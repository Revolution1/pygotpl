#!/bin/sh
set -eu

PROJECT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$PROJECT_DIR"
export GOCACHE="$PROJECT_DIR/.cache/go-build"
export GOMODCACHE="$PROJECT_DIR/.cache/go-mod"
export UV_CACHE_DIR="$PROJECT_DIR/.cache/uv"

EXPECTED_GO_VERSION=go1.27.0
ACTUAL_GO_VERSION=$(go env GOVERSION)
if [ "$ACTUAL_GO_VERSION" != "$EXPECTED_GO_VERSION" ]; then
    echo "Expected $EXPECTED_GO_VERSION, found $ACTUAL_GO_VERSION." >&2
    exit 1
fi

uv sync --frozen --all-packages --extra all --all-groups
uv run --frozen ruff check .
uv run --frozen ruff format --check .
uv run --frozen pyright
uv run --frozen --group docs mkdocs build --strict
uv run --frozen coverage erase
uv run --frozen coverage run -m pytest -q
uv run --frozen coverage report
uv run --frozen coverage json -o coverage-summary.json
uv run --frozen python scripts/check_coverage.py coverage-summary.json
test -z "$(gofmt -l tools/oracle/main.go tools/oracle/sprout_inventory/main.go tools/sprig_oracle/main.go tools/helm_oracle/main.go tools/helm_oracle/benchmark_test.go tools/generate_regex_unicode/main.go tools/gofmt_oracle/main.go tools/goregexp_oracle/main.go benchmarks/go/main.go benchmarks/go/parser.go packages/goduration/tools/oracle/main.go packages/gotime/tools/oracle/main.go)"
./scripts/check_generated.sh
./scripts/check_goduration_oracle.sh
./scripts/check_gofmt_oracle.sh
./scripts/check_goregexp_oracle.sh
./scripts/check_gotime_oracle.sh
./scripts/check_sprout_inventory.sh
go -C tools/oracle test ./...
go -C tools/sprig_oracle test ./...
go -C tools/helm_oracle test ./...
