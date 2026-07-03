#!/bin/sh
set -eu
SELF_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
ROOT=$(CDPATH= cd -- "$SELF_DIR/../.." && pwd)
SOURCE="$ROOT/.agent-loop/cmd/okfctl/main.go"
BINARY="$ROOT/.agent-loop/bin/okfctl.bin"
if ! command -v go >/dev/null 2>&1; then
  echo "build-okfctl: Go 1.21+ is required" >&2
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
"$BINARY" version
