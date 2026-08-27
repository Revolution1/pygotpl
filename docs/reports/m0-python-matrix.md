# Local Python Compatibility Matrix

## Scope

The final August 27, 2026 local matrix exercises the complete unit,
conformance, Python-native, async, property, security, and performance-smoke
test corpus against every supported CPython minor and the current compatible
PyPy release. All runs used the frozen lock file, all optional extras, every
development dependency group, and the Go 1.27.0 oracle on macOS arm64.

## Results

| Interpreter | Full suite | Wheel-only smoke | Result |
| --- | ---: | --- | --- |
| CPython 3.11.16 | 1,970 passed | passed | passed |
| CPython 3.12.14 | 1,970 passed | passed | passed |
| CPython 3.13.15 | 1,970 passed | passed | passed |
| CPython 3.14.7 | 1,970 passed | passed | passed |
| PyPy 3.11.15 / 7.3.23 | 1,966 passed, 4 skipped | passed | passed |

The CPython 3.14 quality gate reports exact 98.1002% statement and 96.0893%
branch coverage across 12,370 statements and 4,526 branches. The PyPy
distribution does not provide `_tracemalloc`; its four skips are the actual
memory-sampling tests for the shared, Jinja, supplementary-engine, and profile
runners. Their unavailable-feature paths are tested, and every template,
async, security, conformance, and benchmark-correctness path executes.
The exact PyPy gate independently reports 98.1214% statement and 96.1114%
branch coverage.

The matrix audit found and fixed two portability defects before these final
runs: Python 3.11 rejected a mapping-proxy dataclass default in the Sprout
registry, and PyPy could not import the Helm benchmark because it imported
`tracemalloc` eagerly. The final suite includes regression coverage for both
corrected boundaries.

Each interpreter also builds the same three `py3-none-any` distributions,
installs the project wheels without source builds, installs only binary runtime
dependencies, removes Go and compiler commands from `PATH`, and executes
`scripts/check_wheel_install.py`. This portable check is now part of every
hosted CPython and PyPy test job.

## CI Coverage

The GitHub Actions configuration mirrors the supported CPython minors across
Linux, macOS, and Windows and includes a separate Linux PyPy 3.11 job. Hosted
results remain pending until the repository is pushed and Actions runs.

## Reproduction

```console
uv run --isolated --python 3.11.16 --frozen --extra all --all-groups pytest -q
uv run --isolated --python 3.12.14 --frozen --extra all --all-groups pytest -q
uv run --isolated --python 3.13.15 --frozen --extra all --all-groups pytest -q
./scripts/check.sh
uv run --isolated --python pypy3.11 --frozen --extra all --all-groups pytest -q -ra
uv run --isolated --python 3.11.16 --frozen --extra all --all-groups python scripts/check_wheel_matrix.py
uv run --isolated --python pypy3.11 --frozen --extra all --all-groups python scripts/check_wheel_matrix.py
```
