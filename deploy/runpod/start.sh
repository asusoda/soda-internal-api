#!/usr/bin/env bash
# Runs the platform on one RunPod pod: API on 8000, dashboard on 5000, MCP server on 8001, bot when BOT_TOKEN is set.
# RUN_BOT=false skips the bot, for a BOT_TOKEN that another bot process already uses.
# The pod clones PLATFORM_BRANCH into /workspace on each start, so a restart deploys the branch head.
# State (SQLite database, generated keys) lives in /workspace/data on the pod's volume.
set -euo pipefail

REPO="${PLATFORM_REPO:-https://github.com/theaisocietyasu/bedrock.git}"
BRANCH="${PLATFORM_BRANCH:-main}"
ROOT=/workspace/platform
DATA=/workspace/data
mkdir -p "$DATA"

if [ -d "$ROOT/.git" ]; then
  git -C "$ROOT" fetch --depth 1 origin "$BRANCH"
  git -C "$ROOT" checkout -q -B "$BRANCH" FETCH_HEAD
else
  git clone --depth 1 --branch "$BRANCH" "$REPO" "$ROOT"
fi
cd "$ROOT"

# Keys generated once and kept on the volume, so sessions and encrypted secrets survive restarts
if [ ! -f "$DATA/keys.env" ]; then
  python3 -c 'import base64, os, secrets; print(f"SECRET_KEY={secrets.token_urlsafe(48)}"); print("SECRETS_KEY=" + base64.urlsafe_b64encode(os.urandom(32)).decode())' > "$DATA/keys.env"
  chmod 600 "$DATA/keys.env"
fi
set -a
# shellcheck disable=SC1091
. "$DATA/keys.env"
set +a

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
