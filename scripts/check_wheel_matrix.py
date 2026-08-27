"""Build and smoke-test the coordinated wheels on the active interpreter."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _run(*arguments: str, environment: dict[str, str] | None = None) -> None:
    subprocess.run(
        arguments,
        cwd=PROJECT_ROOT,
        env=environment,
        check=True,
        timeout=300,
    )


def main() -> None:
    """Verify universal wheels without optional packages or build tools at runtime."""

    uv = shutil.which("uv")
    if uv is None:
        raise RuntimeError("wheel matrix check requires uv")

    with tempfile.TemporaryDirectory(prefix="gotpl-wheel-matrix-") as temporary:
        root = Path(temporary)
        distributions = root / "dist"
        environment = root / "venv"
        _run(uv, "build", "--all-packages", "--out-dir", str(distributions))
        _run(uv, "venv", "--python", sys.executable, str(environment))
        python = environment / (
            "Scripts/python.exe" if os.name == "nt" else "bin/python"
        )
        _run(
            uv,
            "pip",
            "install",
            "--python",
            str(python),
            "--no-index",
            "--no-deps",
            "--find-links",
            str(distributions),
            "gotpl==0.0.0",
            "goduration==0.0.0",
            "gotime==0.0.0",
        )
        _run(
            uv,
            "pip",
            "install",
            "--python",
            str(python),
            "--only-binary",
            ":all:",
            "tzdata==2026.3",
            "tzlocal==5.4.4",
        )
        runtime_environment = os.environ.copy()
        runtime_environment["PATH"] = str(python.parent)
        _run(
            str(python),
            str(PROJECT_ROOT / "scripts/check_wheel_install.py"),
            environment=runtime_environment,
        )


if __name__ == "__main__":
    main()
