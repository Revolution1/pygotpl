"""Bundle sampled Go/Python comparisons for historical CI artifacts."""

from __future__ import annotations

import argparse
import json
import os
import platform
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import TypedDict

from benchmarks.compare import (
    PROJECT_ROOT,
    SampledComparison,
    compare_samples,
    go_version,
)

FIXTURE_DIR = PROJECT_ROOT / "benchmarks" / "fixtures"
RENDER_FIXTURES = tuple(
    FIXTURE_DIR / name
    for name in (
        "literal.json",
        "text_render.json",
        "html_render.json",
        "sprig_render.json",
        "sprig_duration_render.json",
        "text_cold.json",
        "text_writer.json",
        "named_render.json",
        "named_large_render.json",
    )
)


class HistoryBundle(TypedDict):
    schema_version: int
    generated_at: str
    revision: str
    samples: int
    environment: dict[str, str]
    comparisons: list[SampledComparison]


def _revision() -> str:
    configured = os.environ.get("GITHUB_SHA")
    if configured:
        return configured
    process = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        check=False,
        text=True,
        timeout=10,
    )
    return process.stdout.strip() if process.returncode == 0 else "uncommitted"


def build_history(paths: list[Path], *, samples: int = 7) -> HistoryBundle:
    """Run sampled comparisons and attach stable history metadata."""

    if samples < 1:
        raise ValueError("history sample count must be positive")
    if not paths:
        raise ValueError("history requires at least one benchmark fixture")
    comparisons = [compare_samples(path, samples=samples) for path in paths]
    return HistoryBundle(
        schema_version=1,
        generated_at=datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        revision=_revision(),
        samples=samples,
        environment={
            "python": platform.python_version(),
            "go": go_version(),
            "platform": platform.platform(),
            "machine": platform.machine(),
        },
        comparisons=comparisons,
    )


def main() -> None:
    """Create a machine-readable historical comparison artifact."""

    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture", action="append", type=Path, dest="fixtures")
    parser.add_argument("--samples", type=int, default=7)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    fixtures = (
        list(RENDER_FIXTURES) if arguments.fixtures is None else arguments.fixtures
    )
    encoded = json.dumps(
        build_history(fixtures, samples=arguments.samples),
        indent=2,
        sort_keys=True,
    )
    if arguments.output is None:
        print(encoded)
    else:
        arguments.output.write_text(encoded + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
