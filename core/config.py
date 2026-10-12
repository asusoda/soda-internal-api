import json
import os

from core.log import SentrySettings, get_logger

logger = get_logger(__name__)


def _rate(name: str, default: float) -> float:
    """A sample rate from the environment, from 0 to 1. A bad value gives the default."""
    try:
        value = float(os.environ.get(name, default))
    except ValueError:
        logger.warning("%s is not a number; using %s", name, default)
        return default
    return min(max(value, 0.0), 1.0)


def _service_account() -> dict | None:
    """The deployment Google service account key in GOOGLE_SERVICE_ACCOUNT, a JSON object. None means no default."""
    raw = os.environ.get("GOOGLE_SERVICE_ACCOUNT", "").strip()
    if not raw:
        logger.warning("GOOGLE_SERVICE_ACCOUNT is not set. Only orgs with their own Google key have Google Calendar.")
        return None
    try:
        info = json.loads(raw)
    except json.JSONDecodeError as e:
        logger.warning(
            "GOOGLE_SERVICE_ACCOUNT is not valid JSON (%s). Only orgs with their own Google key have Google Calendar.",
            e,
        )
        return None
    if not isinstance(info, dict):
        logger.warning(
            "GOOGLE_SERVICE_ACCOUNT is not a JSON object. Only orgs with their own Google key have Google Calendar."
        )
        return None
    return info


class Config:
    """The settings from the environment. Doppler sets the environment (docs/operations.md, "Settings")."""

    def __init__(self) -> None:
        try:
            # Discord OAuth app and client URLs
            self.CLIENT_ID = os.environ.get("CLIENT_ID", "test-client-id")
            self.CLIENT_SECRET = os.environ.get("CLIENT_SECRET", "test-client-secret")
            self.REDIRECT_URI = os.environ.get("REDIRECT_URI", "http://localhost:5000/callback")
            self.CLIENT_URL = os.environ.get("CLIENT_URL", "http://localhost:3000")
            # Officer dashboard (dashboard/). Login sends officers back here when they start from it
            self.DASHBOARD_URL = os.environ.get("DASHBOARD_URL", "").rstrip("/")

            # Public URL of the MCP server's /mcp, for OAuth (modules/mcp/oauth.py). Empty gives
            # <ACCOUNTS_BASE_URL>/mcp. Set it when the MCP server has its own host
            self.MCP_PUBLIC_URL = os.environ.get("MCP_PUBLIC_URL", "").strip().rstrip("/")

            self.DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./data/user.db")

            self.BOT_TOKEN = os.environ.get("BOT_TOKEN")

            # Clerk, for member sign-in on the website
            self.CLERK_SECRET_KEY = os.environ.get("CLERK_SECRET_KEY", "test-clerk-secret")
            self.CLERK_AUTHORIZED_PARTIES = os.environ.get(
                "CLERK_AUTHORIZED_PARTIES", "http://localhost:3000,http://localhost:5173"
            )

            # Google Calendar Integration
            self.GOOGLE_SERVICE_ACCOUNT = _service_account()

            self.NOTION_API_KEY = os.environ.get("NOTION_API_KEY", "")
            self.TIMEZONE = os.environ.get("TIMEZONE", "America/Phoenix")

            self.SENTRY_DSN = os.environ.get("SENTRY_DSN")
            self.SENTRY = SentrySettings(
                dsn=self.SENTRY_DSN,
                environment=os.environ.get("SENTRY_ENVIRONMENT", "production"),
                release=os.environ.get("GIT_COMMIT_HASH") or None,
                traces_sample_rate=_rate("SENTRY_TRACES_SAMPLE_RATE", 0.1),
                profiles_sample_rate=_rate("SENTRY_PROFILES_SAMPLE_RATE", 0.0),
                logs_level=os.environ.get("SENTRY_LOGS_LEVEL", "WARNING"),
            )

            # Superadmin config: the Discord user ids in SYS_ADMIN, comma-separated
            self.SUPERADMIN_USER_ID = os.environ.get("SYS_ADMIN")

            # Path prefixes that answer 404 like an unknown route, comma-separated. Empty turns none off
            self.DISABLED_ROUTES = tuple(
                p.strip() for p in os.environ.get("DISABLED_ROUTES", "").split(",") if p.strip()
            )

            # Access checks (modules/auth/access.py): false logs refusals, true enforces them
            self.ACCESS_ENFORCE = os.environ.get("ACCESS_ENFORCE", "false").lower() == "true"

            # The largest request body in MB. Godfather file transfers are up to 100 MB. A bigger body gets 413.
            self.MAX_REQUEST_MB = int(os.environ.get("MAX_REQUEST_MB", "110"))

            # Godfather (modules/godfather): the CLI name members see in messages, and the default pod image.
            # The COMPUTE_ names are the names before the rename.
            self.GODFATHER_CLI_NAME = os.environ.get("GODFATHER_CLI_NAME") or os.environ.get(
                "COMPUTE_CLI_NAME", "godfather"
            )
            self.GODFATHER_POD_IMAGE = (
                os.environ.get("GODFATHER_POD_IMAGE")
                or os.environ.get("COMPUTE_POD_IMAGE")
                or "ghcr.io/theaisocietyasu/godfather-base:latest"
            )

            # LeetCode Daily Bot
            self.LEETCODE_CHANNEL_ID = os.environ.get("LEETCODE_CHANNEL_ID")
            self.LEETCODE_ROLE_PING = os.environ.get("LEETCODE_ROLE_PING")
            self.LEETCODE_DAILY_TIME = os.environ.get("LEETCODE_DAILY_TIME", "09:00")

        except json.JSONDecodeError as e:
            raise RuntimeError(f"Configuration error: {str(e)}") from e


config = Config()


def superadmin_ids() -> frozenset[str]:
    """The Discord user ids in SYS_ADMIN. It takes one id or a comma-separated list."""
    return frozenset(i.strip() for i in str(config.SUPERADMIN_USER_ID or "").split(",") if i.strip())
