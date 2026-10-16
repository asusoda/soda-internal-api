"""OAuth providers members can connect, and the token requests to them. No Flask here.

A provider is on when ACCOUNTS_<NAME>_CLIENT_ID and ACCOUNTS_<NAME>_CLIENT_SECRET are set, along
with ACCOUNTS_BASE_URL (the public URL of this API, which the provider redirects back to).
ACCOUNTS_<NAME>_SCOPES, _AUTHORIZE_URL and _TOKEN_URL override the defaults below. The Canvas URLs
come from ACCOUNTS_CANVAS_URL (the school's Canvas, like https://canvas.example.edu), else from the
canvas_url of the one submodule that sets it.
"""

import datetime
import os
from dataclasses import dataclass, field
from urllib.parse import urlencode

import requests

from core.log import get_logger

logger = get_logger("accounts.providers")

TIMEOUT_SECONDS = 30


@dataclass(frozen=True)
class Defaults:
    authorize_url: str
    token_url: str
    scopes: str
    extra: dict[str, str] = field(default_factory=dict)


DEFAULTS = {
    "google": Defaults(
        "https://accounts.google.com/o/oauth2/v2/auth",
        "https://oauth2.googleapis.com/token",
        "https://www.googleapis.com/auth/calendar.events.readonly",
        {"access_type": "offline", "prompt": "consent", "include_granted_scopes": "true"},
    ),
    "canvas": Defaults("/login/oauth2/auth", "/login/oauth2/token", ""),
    "microsoft": Defaults(
        "https://login.microsoftonline.com/common/oauth2/v2.0/authorize",
        "https://login.microsoftonline.com/common/oauth2/v2.0/token",
        "openid profile offline_access Calendars.Read Mail.Read",
    ),
}


class ProviderError(RuntimeError):
    """A token request failed. `refused` means the provider answered invalid_grant: the grant itself is gone."""

    def __init__(self, message: str, refused: bool = False):
        super().__init__(message)
        self.refused = refused


@dataclass(frozen=True)
class Tokens:
    access_token: str
    refresh_token: str | None
    scopes: str
    expires_at: datetime.datetime | None


def base_url() -> str:
    return os.environ.get("ACCOUNTS_BASE_URL", "").strip().rstrip("/")


@dataclass(frozen=True)
class Provider:
    name: str
    client_id: str
    client_secret: str
    authorize_url: str
    token_url: str
    scopes: str
    extra: dict[str, str]

    @property
    def redirect_uri(self) -> str:
        return f"{base_url()}/api/accounts/{self.name}/callback"

    def consent_url(self, state: str) -> str:
        params = {"client_id": self.client_id, "redirect_uri": self.redirect_uri, "response_type": "code"}
        params["state"] = state
        if self.scopes:
            params["scope"] = self.scopes
        params.update(self.extra)
        return f"{self.authorize_url}?{urlencode(params)}"

    def exchange(self, code: str) -> Tokens:
        form = {"grant_type": "authorization_code", "code": code, "redirect_uri": self.redirect_uri}
        return self._tokens(self._post(form), None)

    def refresh(self, refresh_token: str, previous_scopes: str) -> Tokens:
        body = self._post({"grant_type": "refresh_token", "refresh_token": refresh_token})
        tokens = self._tokens(body, previous_scopes)
        # Providers may leave the refresh token out of a refresh response; the old one still works
        return Tokens(tokens.access_token, tokens.refresh_token or refresh_token, tokens.scopes, tokens.expires_at)

    def _post(self, form: dict) -> dict:
        form = {**form, "client_id": self.client_id, "client_secret": self.client_secret}
        try:
            response = requests.post(self.token_url, data=form, timeout=TIMEOUT_SECONDS)
        except requests.RequestException as e:
            raise ProviderError(f"{self.name} could not be reached") from e
        try:
            body = response.json()
        except ValueError:
            body = {}
        if not isinstance(body, dict):
            body = {}
        if response.status_code >= 400:
            code = str(body.get("error", ""))[:64]
            logger.warning(
                "token request refused provider=%s status=%s error=%s", self.name, response.status_code, code
            )
            raise ProviderError(f"{self.name} refused the token request", refused=code == "invalid_grant")
        return body

    @staticmethod
    def _tokens(body: dict, previous_scopes: str | None) -> Tokens:
        access = body.get("access_token")
        if not isinstance(access, str) or not access:
            raise ProviderError("The provider sent no access token")
        refresh = body.get("refresh_token")
        expires_in = body.get("expires_in")
        expires_at = None
        if isinstance(expires_in, int | float) and not isinstance(expires_in, bool):
            expires_at = datetime.datetime.now(datetime.UTC).replace(tzinfo=None) + datetime.timedelta(
                seconds=int(expires_in)
            )
        scope = body.get("scope")
        return Tokens(
            access_token=access,
            refresh_token=refresh if isinstance(refresh, str) and refresh else None,
            scopes=scope if isinstance(scope, str) else (previous_scopes or ""),
            expires_at=expires_at,
        )


def canvas_url() -> str | None:
    """The school's Canvas: ACCOUNTS_CANVAS_URL, else the canvas_url of the one submodule that sets it."""
    url = os.environ.get("ACCOUNTS_CANVAS_URL", "").strip().rstrip("/")
    if url:
        return url
    from modules.submodules import catalog

    found = {submodule.canvas_url.rstrip("/") for submodule in catalog.SUBMODULES.values() if submodule.canvas_url}
    return found.pop() if len(found) == 1 else None


def get(name: str) -> Provider | None:
    """The provider when it is known and configured, else None."""
    defaults = DEFAULTS.get(name)
    if defaults is None or not base_url():
        return None
    prefix = f"ACCOUNTS_{name.upper()}_"
    client_id = os.environ.get(prefix + "CLIENT_ID", "").strip()
    client_secret = os.environ.get(prefix + "CLIENT_SECRET", "").strip()
    if not client_id or not client_secret:
        return None
    authorize_url, token_url = defaults.authorize_url, defaults.token_url
    if name == "canvas":
        school = canvas_url()
        authorize_url = f"{school}{authorize_url}" if school else ""
        token_url = f"{school}{token_url}" if school else ""
    authorize_url = os.environ.get(prefix + "AUTHORIZE_URL", authorize_url)
    token_url = os.environ.get(prefix + "TOKEN_URL", token_url)
    if not authorize_url or not token_url:
        logger.warning("provider %s has no URLs; set ACCOUNTS_CANVAS_URL", name)
        return None
    return Provider(
        name=name,
        client_id=client_id,
        client_secret=client_secret,
        authorize_url=authorize_url,
        token_url=token_url,
        scopes=os.environ.get(prefix + "SCOPES", defaults.scopes),
        extra=dict(defaults.extra),
    )


def enabled() -> list[str]:
    return [name for name in DEFAULTS if get(name) is not None]


# Discord sign-in that proves the browser belongs to the member a login was started for.

DISCORD_AUTHORIZE = "https://discord.com/oauth2/authorize"
DISCORD_TOKEN = "https://discord.com/api/v10/oauth2/token"  # nosec B105 - a URL, not a password
DISCORD_ME = "https://discord.com/api/v10/users/@me"


def discord_redirect_uri() -> str:
    return f"{base_url()}/api/accounts/discord/callback"


def discord_consent_url(client_id: str, state: str, redirect_uri: str | None = None) -> str:
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri or discord_redirect_uri(),
        "response_type": "code",
        "scope": "identify",
        "state": state,
        "prompt": "none",
    }
    return f"{DISCORD_AUTHORIZE}?{urlencode(params)}"


def discord_user_id(client_id: str, client_secret: str, code: str, redirect_uri: str | None = None) -> str:
    """The Discord user id behind an authorization code."""
    form = {
        "client_id": client_id,
        "client_secret": client_secret,
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri or discord_redirect_uri(),
    }
    try:
        token = requests.post(DISCORD_TOKEN, data=form, timeout=TIMEOUT_SECONDS)
        token.raise_for_status()
        access = token.json()["access_token"]
        me = requests.get(DISCORD_ME, headers={"Authorization": f"Bearer {access}"}, timeout=TIMEOUT_SECONDS)
        me.raise_for_status()
        return str(me.json()["id"])
    except (requests.RequestException, ValueError, KeyError, TypeError) as e:
        raise ProviderError("Discord sign-in failed") from e
