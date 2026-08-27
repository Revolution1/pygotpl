#!/bin/sh
set -eu

PROJECT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
TEMP_FILE=$(mktemp "${TMPDIR:-/tmp}/pygotpl-unicode.XXXXXX")
trap 'rm -f "$TEMP_FILE"' EXIT HUP INT TERM

cd "$PROJECT_DIR"
EXPECTED_GO_VERSION=go1.27.0
ACTUAL_GO_VERSION=$(go env GOVERSION)
if [ "$ACTUAL_GO_VERSION" != "$EXPECTED_GO_VERSION" ]; then
    echo "Expected $EXPECTED_GO_VERSION, found $ACTUAL_GO_VERSION." >&2
    exit 1
fi
go run tools/generate_regex_unicode/main.go "$TEMP_FILE"
cmp src/gotpl/_compat/goregexp/_unicode_tables.py "$TEMP_FILE"
