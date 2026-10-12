#!/bin/sh
# Entrypoint of the API image (api, bot, worker and mcp). It runs the command with the settings from Doppler.
# DOPPLER_TOKEN selects the Doppler config. With a personal token, DOPPLER_PROJECT and DOPPLER_CONFIG select it.
# The values in KEEP come from the image or docker-compose.yml and replace a Doppler value of the same name.
# --no-fallback keeps the secrets off the disk: when Doppler is not available, the container stops.
set -eu

KEEP="IS_PROD,RUN_BOT_IN_API,LOG_FORMAT,FLASK_ENV,FLASK_DEBUG,GIT_COMMIT_HASH"

if [ -n "${DOPPLER_TOKEN:-}" ]; then
  exec doppler run --no-fallback --no-check-version --preserve-env="$KEEP" -- "$@"
fi
if [ "${IS_PROD:-}" = "true" ]; then
  echo "DOPPLER_TOKEN is not set, so this container has no settings. See docs/operations.md, \"Settings\"." >&2
  exit 1
fi
echo "DOPPLER_TOKEN is not set. The app starts with its default settings." >&2
exec "$@"
