#!/bin/sh
set -eu

PROJECT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
TEMP_FILE=$(mktemp "${TMPDIR:-/tmp}/goregexp-oracle.XXXXXX")
trap 'rm -f "$TEMP_FILE"' EXIT HUP INT TERM

cd "$PROJECT_DIR"
export GOCACHE="$PROJECT_DIR/.cache/go-build"
EXPECTED_GO_VERSION=go1.27.0
ACTUAL_GO_VERSION=$(go env GOVERSION)
if [ "$ACTUAL_GO_VERSION" != "$EXPECTED_GO_VERSION" ]; then
    echo "Expected $EXPECTED_GO_VERSION, found $ACTUAL_GO_VERSION." >&2
    exit 1
fi
go -C tools/goregexp_oracle run . >"$TEMP_FILE"
python3 -c 'import json, pathlib, sys; expected = json.loads(pathlib.Path(sys.argv[1]).read_text()); actual = json.loads(pathlib.Path(sys.argv[2]).read_text()); raise SystemExit(0 if expected == actual else "goregexp oracle differs")' tests/internal/goregexp/go-regexp-vectors.json "$TEMP_FILE"
