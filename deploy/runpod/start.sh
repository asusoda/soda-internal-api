#!/usr/bin/env bash
# Runs the platform on one RunPod pod: API on 8000, dashboard on 5000, MCP server on 8001, bot when BOT_TOKEN is set.
# RUN_BOT=false skips the bot, for a BOT_TOKEN that another bot process already uses.
# The pod clones PLATFORM_BRANCH into /workspace on each start, so a restart deploys the branch head.
# State (the SQLite database) lives in /workspace/data on the pod's volume.
# Settings come from Doppler: set DOPPLER_TOKEN in the pod environment. The script runs again in `doppler run`
# with --with-settings, so each command below gets the settings. Doppler values replace pod values of the same name.
set -euo pipefail

REPO="${PLATFORM_REPO:-https://github.com/theaisocietyasu/bedrock.git}"
BRANCH="${PLATFORM_BRANCH:-main}"
ROOT=/workspace/platform
DATA=/workspace/data
mkdir -p "$DATA"

if [ "${1:-}" != "--with-settings" ]; then
  if [ -z "${DOPPLER_TOKEN:-}" ]; then
    echo "Set DOPPLER_TOKEN in the pod environment. See docs/getting-started.md, \"Run it on one RunPod pod\"." >&2
    exit 1
  fi
  if [ -d "$ROOT/.git" ]; then
    git -C "$ROOT" fetch --depth 1 origin "$BRANCH"
    git -C "$ROOT" checkout -q -B "$BRANCH" FETCH_HEAD
  else
    git clone --depth 1 --branch "$BRANCH" "$REPO" "$ROOT"
  fi
  "$ROOT/deploy/install-doppler.sh" /usr/local/bin
  exec doppler run --no-fallback --no-check-version -- bash "$ROOT/deploy/runpod/start.sh" --with-settings
fi
cd "$ROOT"

# Older versions of this script wrote SECRET_KEY and SECRETS_KEY to keys.env. SECRETS_KEY decrypts the stored org
# secrets, so the pod does not start when the SECRETS_KEY list in Doppler does not have the key in that file.
if [ -f "$DATA/keys.env" ]; then
  old_key="$(sed -n 's/^SECRETS_KEY=//p' "$DATA/keys.env")"
  case ",${SECRETS_KEY:-}," in
    *",$old_key,"*)
      echo "Doppler has the SECRETS_KEY of $DATA/keys.env. Remove that file." >&2 ;;
    *)
      echo "Copy SECRET_KEY and SECRETS_KEY from $DATA/keys.env to Doppler, then restart the pod." >&2
      exit 1 ;;
  esac
fi

API_URL="${API_URL:-https://${RUNPOD_POD_ID}-8000.proxy.runpod.net}"
WEB_URL="${WEB_URL:-https://${RUNPOD_POD_ID}-5000.proxy.runpod.net}"
export DATABASE_URL="${DATABASE_URL:-sqlite:///$DATA/user.db}"
export REDIRECT_URI="${REDIRECT_URI:-$API_URL/api/auth/callback}"
export ACCOUNTS_BASE_URL="${ACCOUNTS_BASE_URL:-$API_URL}"
# The MCP server has its own proxy host on the pod, so OAuth cannot use <API_URL>/mcp
export MCP_PUBLIC_URL="${MCP_PUBLIC_URL:-https://${RUNPOD_POD_ID}-8001.proxy.runpod.net/mcp}"
export CLIENT_URL="${CLIENT_URL:-$WEB_URL}"
export DASHBOARD_URL="${DASHBOARD_URL:-$WEB_URL}"
export CORS_EXTRA_ORIGINS="${CORS_EXTRA_ORIGINS:-$WEB_URL}"
export IS_PROD=true FLASK_ENV=production FLASK_DEBUG=0 RUN_BOT_IN_API=false LOG_FORMAT=json

python3 -m pip install -q uv
uv sync --frozen --no-dev
(cd dashboard && npm ci --no-audit --no-fund && VITE_API_URL="$API_URL" npm run build)
uv run alembic upgrade head
# Logs the Discord app of BOT_TOKEN and any setting that is missing. A failure does not stop the start.
uv run flask --app main config check || true

# First boot: create the org named by ORG_PREFIX, ORG_NAME and ORG_GUILD_ID if it does not exist yet
if [ -n "${ORG_PREFIX:-}" ] && [ -n "${ORG_GUILD_ID:-}" ]; then
  if ! uv run flask --app main org list | cut -f2 | grep -qx "$ORG_PREFIX"; then
    uv run flask --app main org create --name "${ORG_NAME:-$ORG_PREFIX}" --prefix "$ORG_PREFIX" \
      --guild-id "$ORG_GUILD_ID" ${ORG_OFFICER_ROLE_ID:+--officer-role-id "$ORG_OFFICER_ROLE_ID"} \
      ${ORG_MODULES_OFF:+--off "$ORG_MODULES_OFF"}
  fi
fi

npx --yes serve@14 -s dashboard/dist -l 5000 &
uv run python mcp_main.py &
if [ -n "${BOT_TOKEN:-}" ] && [ "${RUN_BOT:-true}" != "false" ]; then
  uv run python bot_main.py &
fi
exec uv run gunicorn --workers 1 --threads 8 --timeout 120 --bind 0.0.0.0:8000 main:app
