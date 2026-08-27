#!/bin/sh
set -eu

PROJECT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
BUILD_ROOT=$(mktemp -d "${TMPDIR:-/tmp}/gotpl-reproducible-build.XXXXXX")
FIRST_DIR="$BUILD_ROOT/first"
SECOND_DIR="$BUILD_ROOT/second"

cleanup() {
    rm -rf -- "$BUILD_ROOT"
}
trap cleanup EXIT HUP INT TERM

mkdir "$FIRST_DIR" "$SECOND_DIR"
cd "$PROJECT_DIR"

export SOURCE_DATE_EPOCH=${SOURCE_DATE_EPOCH:-1704067200}
uv build --all-packages --out-dir "$FIRST_DIR"
uv build --all-packages --out-dir "$SECOND_DIR"

artifact_count=0
for artifact in "$FIRST_DIR"/*; do
    name=${artifact##*/}
    counterpart="$SECOND_DIR/$name"
    test -f "$counterpart"
    if ! cmp "$artifact" "$counterpart"; then
        echo "Artifact is not reproducible: $name" >&2
        exit 1
    fi
    artifact_count=$((artifact_count + 1))
done

test "$artifact_count" -eq 6
second_artifact_count=0
for _artifact in "$SECOND_DIR"/*; do
    second_artifact_count=$((second_artifact_count + 1))
done
test "$second_artifact_count" -eq 6
echo "Verified six reproducible wheel and source-distribution artifacts."
