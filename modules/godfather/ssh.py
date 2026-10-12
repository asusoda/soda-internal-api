"""SSH keys and short-lived user certificates for pod access. No Flask and no ssh-keygen here.

Pods built from an image that implements the pod contract (GODFATHER_POD_IMAGE) trust the org's
user CA and accept a certificate whose principal is gf-<pod id>. A member certificate carries a forced command that drops the member into
their own account; an officer certificate is root.
"""

import datetime
import re

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import dsa, ed25519
from cryptography.hazmat.primitives.serialization import SSHCertificateBuilder, SSHCertificateType

# Forced command and principal prefix the pod image expects; part of the pod image contract.
LOGIN_COMMAND = "/usr/local/bin/godfather-login"
CERT_BEFORE = datetime.timedelta(minutes=5)
CERT_AFTER = datetime.timedelta(hours=12)
ALLOWED_KEY_TYPES = (
    "ssh-ed25519",
    "ssh-rsa",
    "ecdsa-sha2-nistp256",
    "ecdsa-sha2-nistp384",
    "ecdsa-sha2-nistp521",
)
PUBLIC_KEY_RE = re.compile(r"^[a-z0-9-]+ [A-Za-z0-9+/=]+( [\x21-\x7e ]{0,200})?$")


def pod_principal(pod_id: str) -> str:
    """The certificate principal a pod accepts."""
    return f"gf-{pod_id}"


def safe_username(name: str) -> str:
    """A Discord username reduced to characters safe for a Unix account and a path."""
    cleaned = re.sub(r"[^a-z0-9._-]", "", (name or "").lower()).lstrip(".-")[:22]
    return cleaned or "user"


def is_valid_public_key(public_key: object) -> bool:
    """A single-line OpenSSH public key of a supported type."""
    if not isinstance(public_key, str) or len(public_key) > 4096 or "\n" in public_key.strip():
        return False
    key = public_key.strip()
    if not PUBLIC_KEY_RE.match(key) or key.split(" ", 1)[0] not in ALLOWED_KEY_TYPES:
        return False
    try:
        serialization.load_ssh_public_key(key.encode())
    except (ValueError, TypeError):
        return False
    return True


def generate_keypair(comment: str) -> tuple[str, str]:
    """A new ed25519 key pair: (OpenSSH public key, OpenSSH private key)."""
    private = ed25519.Ed25519PrivateKey.generate()
    public = private.public_key().public_bytes(serialization.Encoding.OpenSSH, serialization.PublicFormat.OpenSSH)
    private_text = private.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.OpenSSH, serialization.NoEncryption()
    )
    return f"{public.decode()} {comment}", private_text.decode().strip()


def sign_user_key(
    ca_private_key: str,
    public_key: str,
    pod_id: str,
    discord_id: str,
    username: str,
    is_admin: bool,
    now: datetime.datetime | None = None,
) -> str:
    """A certificate for a member's own public key, valid for one pod for twelve hours."""
    if not is_valid_public_key(public_key):
        raise ValueError("Invalid SSH public key")
    ca = serialization.load_ssh_private_key(ca_private_key.encode(), password=None)
    subject = serialization.load_ssh_public_key(public_key.strip().encode())
    # SSH certificates cannot hold or be signed by DSA keys
    if isinstance(ca, dsa.DSAPrivateKey):
        raise ValueError("The CA key is a DSA key, which cannot sign SSH certificates")
    if isinstance(subject, dsa.DSAPublicKey):
        raise ValueError("Invalid SSH public key")
    username = safe_username(username)
    now = now or datetime.datetime.now(datetime.UTC)
    builder = (
        SSHCertificateBuilder()
        .public_key(subject)
        .type(SSHCertificateType.USER)
        .key_id(f"discord:{discord_id}:{username}".encode())
        .valid_principals([pod_principal(pod_id).encode()])
        .valid_after(int((now - CERT_BEFORE).timestamp()))
        .valid_before(int((now + CERT_AFTER).timestamp()))
        .add_extension(b"permit-pty", b"")
        .add_extension(b"permit-port-forwarding", b"")
    )
    if is_admin:
        builder = builder.add_extension(b"permit-agent-forwarding", b"")
    else:
        builder = builder.add_critical_option(b"force-command", f"{LOGIN_COMMAND} {username}".encode())
    certificate = builder.sign(ca)
    return certificate.public_bytes().decode()
