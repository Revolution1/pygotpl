#!/bin/sh
set -eu

PROJECT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
TEMP_FILE=$(mktemp "${TMPDIR:-/tmp}/sprout-inventory.XXXXXX")
trap 'rm -f "$TEMP_FILE"' EXIT HUP INT TERM

cd "$PROJECT_DIR"
export GOCACHE="$PROJECT_DIR/.cache/go-build"
export GOMODCACHE="$PROJECT_DIR/.cache/go-mod"
EXPECTED_GO_VERSION=go1.27.0
ACTUAL_GO_VERSION=$(go env GOVERSION)
if [ "$ACTUAL_GO_VERSION" != "$EXPECTED_GO_VERSION" ]; then
    echo "Expected $EXPECTED_GO_VERSION, found $ACTUAL_GO_VERSION." >&2
    exit 1
fi

go -C tools/oracle run ./sprout_inventory -output "$TEMP_FILE"
python3 -c 'import json, pathlib, sys; expected = json.loads(pathlib.Path(sys.argv[1]).read_text()); actual = json.loads(pathlib.Path(sys.argv[2]).read_text()); raise SystemExit(0 if expected == actual else "Sprout inventory oracle differs")' docs/reports/sprout-v1.1.1-inventory.json "$TEMP_FILE"
python3 -c 'import json, pathlib, sys; expected = json.loads(pathlib.Path(sys.argv[1]).read_text()); actual = json.loads(pathlib.Path(sys.argv[2]).read_text()); raise SystemExit(0 if expected == actual else "packaged Sprout inventory differs")' src/gotpl/funcs/sprout/data/sprout-v1.1.1-inventory.json "$TEMP_FILE"
