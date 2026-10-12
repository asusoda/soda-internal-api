"""Client keys for MCP OAuth: private_key_jwt client authentication (RFC 7523). No Flask here.

A client with token_endpoint_auth_method private_key_jwt publishes public keys in its Client ID Metadata
Document, as jwks or jwks_uri. At /token and /revoke it sends client_assertion, a JWT that it signs with its
private key. Platform checks the signature, the claims and that the jti was not used before.

The mcp SDK's ClientAuthenticator does not support private_key_jwt, so ClientAuthenticator here replaces it on
those two routes and leaves the other methods to the SDK.
"""

import base64
import datetime
import hashlib
import hmac
import json
import threading
import time
from typing import Any, cast
from urllib.parse import unquote

import jwt
from anyio import to_thread
from mcp.server.auth.middleware import client_auth as sdk_client_auth
from sqlalchemy.exc import IntegrityError

from core.db import db_connect
from core.log import get_logger
from core.time import utcnow
from modules.mcp import oauth
from modules.mcp.models import OAuthAssertion

logger = get_logger(__name__)

ASSERTION_TYPE = "urn:ietf:params:oauth:client-assertion-type:jwt-bearer"
# Asymmetric algorithms only: a client that shares a secret is not a key client
ALGORITHMS = ("RS256", "RS384", "RS512", "PS256", "PS384", "PS512", "ES256", "ES384", "ES512", "EdDSA")
MAX_LIFETIME_SECONDS = 300
LEEWAY_SECONDS = 30
JWKS_MAX_BYTES = 20 * 1024
# A key set is fetched again for an unknown kid, but not more often than this
JWKS_REFETCH_SECONDS = 60
# Members of a JWK that only a private key has
PRIVATE_MEMBERS = ("d", "p", "q", "dp", "dq", "qi", "oth", "k")

JWKS_MAX_ENTRIES = 1000
# url -> (until, fetched_at, key set). None for a fetch that failed, so that it is not tried again at once
_jwks_cache: dict[str, tuple[float, float, dict | None]] = {}
_jwks_lock = threading.Lock()


class InvalidAssertion(ValueError):
    """The client assertion is not valid."""


# The key type (kty) that each algorithm needs
KEY_TYPES = {"RS": "RSA", "PS": "RSA", "ES": "EC", "Ed": "OKP"}


def parse_keys(jwks: object) -> list[tuple[dict, jwt.PyJWK]]:
    """The signing keys of a JWK set, each with its JSON. Raises oauth.OAuthError for a set that is not valid or
    has private keys."""
    found = cast(dict, jwks).get("keys") if isinstance(jwks, dict) else None
    if not isinstance(found, list) or not found:
        raise oauth.OAuthError("jwks must be a JWK set with one or more keys")
    keys = []
    for item in found:
        if not isinstance(item, dict):
            raise oauth.OAuthError("Each key of jwks must be a JSON object")
        if any(member in item for member in PRIVATE_MEMBERS):
            raise oauth.OAuthError("jwks must have public keys only")
        if item.get("use") not in (None, "sig"):
            continue
        try:
            keys.append((item, jwt.PyJWK(item)))
        except (jwt.PyJWKError, jwt.InvalidKeyError) as e:
            raise oauth.OAuthError(f"A key of jwks is not valid: {e}") from e
    if not keys:
        raise oauth.OAuthError("jwks has no key for signatures")
    return keys


def fetch_jwks(url: str) -> oauth.Fetched:
    return oauth.fetch_public(url, JWKS_MAX_BYTES)


def _remote_keys(url: str, *, refresh: bool = False) -> list[tuple[dict, jwt.PyJWK]]:
    """The keys at a jwks_uri, cached for the time its headers allow. refresh fetches again after a short wait.

    A failed fetch is kept for JWKS_REFETCH_SECONDS, so requests in that time fail at once.
    """
    now = time.monotonic()
    with _jwks_lock:
        found = _jwks_cache.get(url)
    if found is not None:
        until, fetched_at, jwks = found
        if jwks is None and now < until:
            raise oauth.OAuthError(f"{url} failed a moment ago. Try again later")
        if jwks is not None and now < until and not (refresh and now - fetched_at > JWKS_REFETCH_SECONDS):
            return parse_keys(jwks)
    try:
        fetched = fetch_jwks(url)
        if fetched.status != 200 or len(fetched.body) > JWKS_MAX_BYTES:
            raise oauth.OAuthError(f"{url} returned {fetched.status} or is too large")
        try:
            jwks = json.loads(fetched.body)
        except ValueError as e:
            raise oauth.OAuthError(f"{url} is not JSON") from e
        keys = parse_keys(jwks)
    except oauth.OAuthError:
        _store(url, now + JWKS_REFETCH_SECONDS, now, None)
        raise
    _store(url, now + oauth.cache_time(fetched.headers).total_seconds(), now, jwks)
    return keys


def _store(url: str, until: float, fetched_at: float, jwks: dict | None) -> None:
    """Keep a key set or a failure. Past JWKS_MAX_ENTRIES, expired entries go first, then the oldest."""
    with _jwks_lock:
        _jwks_cache[url] = (until, fetched_at, jwks)
        if len(_jwks_cache) <= JWKS_MAX_ENTRIES:
            return
        for key in [k for k, v in _jwks_cache.items() if v[0] <= fetched_at and k != url]:
            del _jwks_cache[key]
        while len(_jwks_cache) > JWKS_MAX_ENTRIES:
            oldest = min((k for k in _jwks_cache if k != url), key=lambda k: _jwks_cache[k][1])
            del _jwks_cache[oldest]


def clear_cache() -> None:
    with _jwks_lock:
        _jwks_cache.clear()


def _keys(client: dict, *, refresh: bool = False) -> list[tuple[dict, jwt.PyJWK]]:
    if client.get("jwks_uri"):
        return _remote_keys(str(client["jwks_uri"]), refresh=refresh)
    return parse_keys(client.get("jwks"))


def _candidates(keys: list[tuple[dict, jwt.PyJWK]], header: dict) -> list[jwt.PyJWK]:
    """The keys that can check a JWT with this header: its kid if it has one, the key type of its alg, and the
    alg of the key if the key names one."""
    kid, alg = header.get("kid"), str(header.get("alg"))
    kty = KEY_TYPES.get(alg[:2])
    return [
        key
        for data, key in keys
        if (kid is None or data.get("kid") == kid) and data.get("kty") == kty and data.get("alg") in (None, alg)
    ]


def _audiences() -> list[str]:
    public = oauth.public_url()
    return [public, f"{public}/token", f"{public}/revoke"]


def verify_assertion(db, client: dict, assertion: str) -> None:
    """Check a client assertion against the client's keys and record its jti. Raises InvalidAssertion. Commits."""
    client_id = str(client["client_id"])
    try:
        header = jwt.get_unverified_header(assertion)
    except jwt.PyJWTError as e:
        raise InvalidAssertion("client_assertion is not a JWT") from e
    alg = header.get("alg")
    allowed = client.get("token_endpoint_auth_signing_alg")
    if alg not in ALGORITHMS or (allowed and alg != allowed):
        raise InvalidAssertion(f"client_assertion alg {alg} is not allowed")
    try:
        candidates = _candidates(_keys(client), header)
        if not candidates and header.get("kid"):
            candidates = _candidates(_keys(client, refresh=True), header)
    except oauth.OAuthError as e:
        raise InvalidAssertion(f"The keys of the client cannot be read: {e}") from e
    claims: dict[str, Any] | None = None
    for key in candidates:
        try:
            claims = jwt.decode(
                assertion,
                key.key,
                algorithms=[str(alg)],
                audience=_audiences(),
                issuer=client_id,
                leeway=LEEWAY_SECONDS,
                options={"require": ["exp", "iss", "sub", "aud", "jti"]},
            )
            break
        except jwt.InvalidSignatureError:
            continue
        except jwt.PyJWTError as e:
            raise InvalidAssertion(f"client_assertion is not valid: {e}") from e
    if claims is None:
        raise InvalidAssertion("client_assertion is not signed with a key of the client")
    if claims.get("sub") != client_id:
        raise InvalidAssertion("client_assertion sub must be the client_id")
    now = time.time()
    if float(claims["exp"]) > now + MAX_LIFETIME_SECONDS + LEEWAY_SECONDS:
        raise InvalidAssertion(f"client_assertion must expire within {MAX_LIFETIME_SECONDS} seconds")
    _use_once(db, client_id, str(claims["jti"]), float(claims["exp"]))


def _use_once(db, client_id: str, jti: str, exp: float) -> None:
    jti_hash = hashlib.sha256(f"{client_id}\n{jti}".encode()).hexdigest()
    expires = datetime.datetime.fromtimestamp(exp + LEEWAY_SECONDS, datetime.UTC).replace(tzinfo=None)
    db.add(OAuthAssertion(jti_hash=jti_hash, expires_at=expires))
    try:
        db.commit()
    except IntegrityError as e:
        db.rollback()
        raise InvalidAssertion("client_assertion was used before") from e


def cleanup(db) -> int:
    """Delete the jti of expired assertions. Commits."""
    deleted = db.query(OAuthAssertion).filter(OAuthAssertion.expires_at <= utcnow()).delete()
    db.commit()
    return deleted


def _verify(client: dict, assertion: str) -> None:
    db = db_connect.SessionLocal()
    try:
        verify_assertion(db, client, assertion)
    finally:
        db.close()


def basic_credentials(header: str) -> tuple[str, str] | None:
    """The client_id and client_secret of an HTTP Basic header (RFC 6749 2.3.1), or None."""
    if not header.lower().startswith("basic "):
        return None
    try:
        decoded = base64.b64decode(header[6:].strip(), validate=True).decode("utf-8")
    except (ValueError, UnicodeDecodeError):
        return None
    client_id, sep, secret = decoded.partition(":")
    return (unquote(client_id), unquote(secret)) if sep else None


class ClientAuthenticator(sdk_client_auth.ClientAuthenticator):
    """Client authentication for /token and /revoke: a client secret, private_key_jwt, or none.

    A client with a secret may send it in the Basic header or in the form, whatever method it registered:
    RFC 7591 makes client_secret_basic the default, and the SDK records client_secret_post, so a client that
    follows the RFC would else get 401. client_id may come from the Basic header alone (RFC 6749 2.3.1).
    """

    async def authenticate_request(self, request):
        form = await request.form()
        assertion_type, assertion = form.get("client_assertion_type"), form.get("client_assertion")
        # RFC 6749 2.3: one client authentication method in each request
        methods = [
            basic_credentials(request.headers.get("authorization", "")) is not None,
            bool(form.get("client_secret")),
            assertion_type is not None or assertion is not None,
        ]
        if sum(methods) > 1:
            raise sdk_client_auth.AuthenticationError("Use one client authentication method per request")
        if assertion_type is None and assertion is None:
            return await self._secret_or_none(request, form)
        if assertion_type != ASSERTION_TYPE or not isinstance(assertion, str) or not assertion:
            raise sdk_client_auth.AuthenticationError(f"client_assertion_type must be {ASSERTION_TYPE}")
        client_id = form.get("client_id")
        if not isinstance(client_id, str) or not client_id:
            raise sdk_client_auth.AuthenticationError("Missing client_id")
        client = await self.provider.get_client(client_id)
        if client is None or client.token_endpoint_auth_method != oauth.KEY_CLIENT:
            raise sdk_client_auth.AuthenticationError("This client does not use private_key_jwt")
        try:
            await to_thread.run_sync(_verify, client.model_dump(mode="json"), assertion)
        except InvalidAssertion as e:
            logger.warning("client assertion refused client_id=%s: %s", client_id, e)
            raise sdk_client_auth.AuthenticationError(str(e)) from e
        return client

    async def _secret_or_none(self, request, form):
        basic = basic_credentials(request.headers.get("authorization", ""))
        form_id = form.get("client_id")
        client_id = form_id if isinstance(form_id, str) and form_id else (basic[0] if basic else None)
        if not client_id:
            raise sdk_client_auth.AuthenticationError("Missing client_id")
        if basic and basic[0] != client_id:
            raise sdk_client_auth.AuthenticationError("Client ID mismatch in Basic auth")
        client = await self.provider.get_client(client_id)
        if client is None:
            raise sdk_client_auth.AuthenticationError("Invalid client_id")
        if client.token_endpoint_auth_method == oauth.KEY_CLIENT:
            raise sdk_client_auth.AuthenticationError("This client must send client_assertion")
        if not client.client_secret:
            if client.token_endpoint_auth_method not in (None, oauth.PUBLIC_CLIENT):
                raise sdk_client_auth.AuthenticationError("The client has no stored secret")
            return client
        form_secret = form.get("client_secret")
        secret = basic[1] if basic else (form_secret if isinstance(form_secret, str) else None)
        if not secret:
            raise sdk_client_auth.AuthenticationError("Client secret is required")
        if not hmac.compare_digest(client.client_secret.encode(), secret.encode()):
            raise sdk_client_auth.AuthenticationError("Invalid client_secret")
        if client.client_secret_expires_at and client.client_secret_expires_at < int(time.time()):
            raise sdk_client_auth.AuthenticationError("Client secret has expired")
        return client
