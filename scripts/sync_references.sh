#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
PROJECT_DIR=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)
REFERENCE_DIR=${PYGOTPL_REFERENCE_DIR:-"$PROJECT_DIR/.references"}

GO_REVISION=go1.27.0
SPRIG_REVISION=v3.3.0
SPROUT_REVISION=v1.1.1
SLIM_SPRIG_REVISION=v3.0.0
HELM_REVISION=v4.2.3

ensure_revision() {
    repository_dir=$1
    expected_revision=$2

    actual_revision=$(git -C "$repository_dir" describe --tags --exact-match 2>/dev/null || true)
    if [ "$actual_revision" != "$expected_revision" ]; then
        echo "Reference at $repository_dir is not pinned to $expected_revision." >&2
        exit 1
    fi
}

mkdir -p "$REFERENCE_DIR"

if [ ! -d "$REFERENCE_DIR/go/.git" ]; then
    git clone \
        --depth 1 \
        --branch "$GO_REVISION" \
        --filter=blob:none \
        --sparse \
        https://go.googlesource.com/go \
        "$REFERENCE_DIR/go"
    git -C "$REFERENCE_DIR/go" sparse-checkout set \
        src/text/template \
        src/html/template \
        src/fmt \
        src/time
fi
git -C "$REFERENCE_DIR/go" sparse-checkout set \
    src/text/template \
    src/html/template \
    src/fmt \
    src/time
ensure_revision "$REFERENCE_DIR/go" "$GO_REVISION"

if [ ! -d "$REFERENCE_DIR/sprig/.git" ]; then
    git clone \
        --depth 1 \
        --branch "$SPRIG_REVISION" \
        https://github.com/Masterminds/sprig.git \
        "$REFERENCE_DIR/sprig"
fi
ensure_revision "$REFERENCE_DIR/sprig" "$SPRIG_REVISION"

if [ ! -d "$REFERENCE_DIR/sprout/.git" ]; then
    git clone \
        --depth 1 \
        --branch "$SPROUT_REVISION" \
        https://github.com/go-sprout/sprout.git \
        "$REFERENCE_DIR/sprout"
fi
ensure_revision "$REFERENCE_DIR/sprout" "$SPROUT_REVISION"

if [ ! -d "$REFERENCE_DIR/slim-sprig/.git" ]; then
    git clone \
        --depth 1 \
        --branch "$SLIM_SPRIG_REVISION" \
        https://github.com/go-task/slim-sprig.git \
        "$REFERENCE_DIR/slim-sprig"
fi
ensure_revision "$REFERENCE_DIR/slim-sprig" "$SLIM_SPRIG_REVISION"

if [ ! -d "$REFERENCE_DIR/helm/.git" ]; then
    git clone \
        --depth 1 \
        --branch "$HELM_REVISION" \
        --filter=blob:none \
        --sparse \
        https://github.com/helm/helm.git \
        "$REFERENCE_DIR/helm"
    git -C "$REFERENCE_DIR/helm" sparse-checkout set \
        pkg/action \
        internal/chart/v3 \
        internal/copystructure \
        internal/version \
        pkg/chart/common \
        pkg/chart/v2 \
        pkg/engine
fi
git -C "$REFERENCE_DIR/helm" sparse-checkout set \
    pkg/action \
    internal/chart/v3 \
    internal/copystructure \
    internal/version \
    pkg/chart/common \
    pkg/chart/v2 \
    pkg/engine
ensure_revision "$REFERENCE_DIR/helm" "$HELM_REVISION"

echo "Go reference: $GO_REVISION"
echo "Sprig reference: $SPRIG_REVISION"
echo "Sprout reference: $SPROUT_REVISION"
echo "Slim-Sprig reference: $SLIM_SPRIG_REVISION"
echo "Helm reference: $HELM_REVISION"
