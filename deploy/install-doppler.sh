#!/usr/bin/env bash
# Installs the pinned Doppler CLI in the directory in $1 (default /usr/local/bin) and checks its sha256.
# Dockerfile.api, deploy/runpod/start.sh and .agents/setup use it. To change the version, change the
# version and both sums from checksums.txt of the release at https://github.com/DopplerHQ/cli/releases.
set -euo pipefail

VERSION=3.77.0
DEST="${1:-/usr/local/bin}"

case "$(uname -m)" in
  x86_64 | amd64) arch=amd64 sum=92587cb89c2ff82fc2ddec2b2a9f275ff320994a44e16cd9310b55a429a82084 ;;
  aarch64 | arm64) arch=arm64 sum=3aa603d60bc8502ec67d9a57e917925f357ac2822eead484acda3875fe6a4d95 ;;
  *) echo "No Doppler CLI build for $(uname -m)" >&2; exit 1 ;;
esac

if [ -x "$DEST/doppler" ] && [ "$("$DEST/doppler" --version 2>/dev/null)" = "v$VERSION" ]; then
  echo "Doppler CLI v$VERSION is installed"
  exit 0
fi

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
tarball="doppler_${VERSION}_linux_${arch}.tar.gz"
curl -fsSL --proto '=https' --retry 3 -o "$tmp/$tarball" \
  "https://github.com/DopplerHQ/cli/releases/download/$VERSION/$tarball"
echo "$sum  $tmp/$tarball" | sha256sum -c --quiet -
tar -xzf "$tmp/$tarball" -C "$tmp" doppler
mkdir -p "$DEST"
install -m 0755 "$tmp/doppler" "$DEST/doppler"
echo "Installed Doppler CLI v$VERSION in $DEST"
