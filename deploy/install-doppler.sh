#!/usr/bin/env bash
# Installs the pinned Doppler CLI in the directory in $1 (default /usr/local/bin) and checks its sha256.
# Dockerfile.api, deploy/runpod/start.sh and .agents/setup use it. To change the version, change the
# version and the four sums from checksums.txt of the release at https://github.com/DopplerHQ/cli/releases.
set -euo pipefail

VERSION=3.77.0
DEST="${1:-/usr/local/bin}"

case "$(uname -s)-$(uname -m)" in
  Linux-x86_64 | Linux-amd64) build=linux_amd64 sum=92587cb89c2ff82fc2ddec2b2a9f275ff320994a44e16cd9310b55a429a82084 ;;
  Linux-aarch64 | Linux-arm64) build=linux_arm64 sum=3aa603d60bc8502ec67d9a57e917925f357ac2822eead484acda3875fe6a4d95 ;;
  Darwin-x86_64) build=macOS_amd64 sum=315c09fdd5306d781057705f2180e2e0719c7fb6a3df8982cbfd593234278c8a ;;
  Darwin-arm64) build=macOS_arm64 sum=19e1f7ff2655e3bb5ea1ba9892de5a5a74de6a7a6f021e1f63f30627d5936f13 ;;
  *) echo "No Doppler CLI build for $(uname -s) $(uname -m)" >&2; exit 1 ;;
esac

if [ -x "$DEST/doppler" ] && [ "$("$DEST/doppler" --version 2>/dev/null)" = "v$VERSION" ]; then
  echo "Doppler CLI v$VERSION is installed"
  exit 0
fi

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
tarball="doppler_${VERSION}_${build}.tar.gz"
curl -fsSL --proto '=https' --retry 3 -o "$tmp/$tarball" \
  "https://github.com/DopplerHQ/cli/releases/download/$VERSION/$tarball"
# macOS has shasum and no sha256sum
if command -v sha256sum > /dev/null; then
  echo "$sum  $tmp/$tarball" | sha256sum -c --quiet -
else
  echo "$sum  $tmp/$tarball" | shasum -a 256 -c --quiet -
fi
tar -xzf "$tmp/$tarball" -C "$tmp" doppler
mkdir -p "$DEST"
install -m 0755 "$tmp/doppler" "$DEST/doppler"
echo "Installed Doppler CLI v$VERSION in $DEST"
