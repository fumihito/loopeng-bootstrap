#!/bin/sh
set -eu
SELF_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
ROOT=$(CDPATH= cd -- "$SELF_DIR/../.." && pwd)
SOURCE="$ROOT/.agent-loop/cmd/okfctl/main.go"
BINARY="$ROOT/.agent-loop/bin/okfctl.bin"
SHA_FILE="$ROOT/.agent-loop/bin/okfctl.bin.sha256"
if ! command -v go >/dev/null 2>&1; then
  echo "build-okfctl: Go is not installed" >&2
  exit 1
fi
TMP="$BINARY.tmp.$$"
trap 'rm -f "$TMP"' EXIT HUP INT TERM
GOCACHE="${GOCACHE:-/tmp/loopeng-gocache}"
mkdir -p "$GOCACHE"
GOWORK=off GOCACHE="$GOCACHE" go build -trimpath -ldflags='-s -w' -o "$TMP" "$SOURCE"
chmod 0755 "$TMP"
mv "$TMP" "$BINARY"
trap - EXIT HUP INT TERM
# This checksum only detects accidental drift in the local build tree; it is not a tamper-proof trust boundary.
sha256sum "$BINARY" | awk '{print $1 "  okfctl.bin"}' > "$SHA_FILE"
"$BINARY" version
