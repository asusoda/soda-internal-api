#!/bin/sh
# Entrypoint of the API image (api, bot, worker and mcp). It runs the command with the settings from Doppler.
# DOPPLER_TOKEN selects the Doppler config. With a personal token, DOPPLER_PROJECT and DOPPLER_CONFIG select it.
# A value that the image or docker-compose.yml sets, such as IS_PROD or RUN_BOT_IN_API, stays.
# --no-fallback keeps the secrets off the disk: when Doppler is not available, the container stops.
set -eu

if [ -n "${DOPPLER_TOKEN:-}" ]; then
  exec doppler run --no-fallback --no-check-version --preserve-env=true -- "$@"
fi
if [ "${IS_PROD:-}" = "true" ]; then
  echo "DOPPLER_TOKEN is not set, so this container has no settings. See docs/operations.md, \"Settings\"." >&2
  exit 1
fi
echo "DOPPLER_TOKEN is not set. The app starts with its default settings." >&2
exec "$@"
