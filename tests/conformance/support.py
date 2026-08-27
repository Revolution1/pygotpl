from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import NotRequired, TypedDict, cast

import pytest

PROJECT_ROOT = Path(__file__).parents[2]
FIXTURE_ROOT = Path(__file__).parent / "fixtures"
ORACLE_ROOT = PROJECT_ROOT / "tools" / "oracle"
SPRIG_ORACLE_ROOT = PROJECT_ROOT / "tools" / "sprig_oracle"


class ReferenceMetadata(TypedDict):
    project: str
    revision: str
    source: str
    behavior: str
    derived: bool


class TemplateRequest(TypedDict):
    engine: str
    name: str
    template: str
    data: object
    delimiters: NotRequired[dict[str, str]]
    options: NotRequired[list[str]]
    function_profile: NotRequired[str]
    execute_template: NotRequired[str]


class ErrorResult(TypedDict):
    phase: str
    message: NotRequired[str]


class ExpectedResult(TypedDict):
    output: str
    error: ErrorResult | None


@dataclass(frozen=True, slots=True)
class Fixture:
    identifier: str
    reference: ReferenceMetadata
    request: TemplateRequest
    expected: ExpectedResult


def load_fixture(path: Path) -> Fixture:
    raw: object = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise AssertionError(f"fixture {path} must contain an object")
    raw_dict = cast(dict[str, object], raw)
    required = {"schema_version", "id", "reference", "request", "expected"}
    if set(raw_dict) != required:
        raise AssertionError(f"fixture {path} has invalid top-level keys")
    if raw_dict["schema_version"] != 1:
        raise AssertionError(f"fixture {path} has an unsupported schema version")
    identifier = raw_dict["id"]
    reference = raw_dict["reference"]
    request = raw_dict["request"]
    expected = raw_dict["expected"]
    if not isinstance(identifier, str):
        raise AssertionError(f"fixture {path} has an invalid id")
    if not all(isinstance(value, dict) for value in (reference, request, expected)):
        raise AssertionError(f"fixture {path} contains an invalid object")
    return Fixture(
        identifier,
        cast(ReferenceMetadata, reference),
        cast(TemplateRequest, request),
        cast(ExpectedResult, expected),
    )


def run_go_oracle(request: TemplateRequest) -> ExpectedResult:
    return run_go_oracle_many([request])[0]


def run_go_oracle_many(requests: list[TemplateRequest]) -> list[ExpectedResult]:
    """Execute multiple oracle requests in one Go process."""

    if shutil.which("go") is None:
        pytest.skip("the Go conformance oracle requires the Go toolchain")
    environment = os.environ.copy()
    environment["GOCACHE"] = str(PROJECT_ROOT / ".cache" / "go-build")
    environment["GOMODCACHE"] = str(PROJECT_ROOT / ".cache" / "go-mod")
    oracle_root = (
        SPRIG_ORACLE_ROOT
        if requests
        and all(
            request.get("function_profile", "") in {"sprig", "sprig-hermetic"}
            for request in requests
        )
        else ORACLE_ROOT
    )
    process = subprocess.run(
        ["go", "run", "."],
        cwd=oracle_root,
        env=environment,
        input="\n".join(json.dumps(request) for request in requests),
        capture_output=True,
        check=False,
        text=True,
        timeout=60,
    )
    if process.returncode != 0:
        raise AssertionError(f"Go oracle failed: {process.stderr}")
    results: list[ExpectedResult] = []
    for line in process.stdout.splitlines():
        result: object = json.loads(line)
        if not isinstance(result, dict):
            raise AssertionError("Go oracle returned a non-object result")
        results.append(cast(ExpectedResult, result))
    if len(results) != len(requests):
        raise AssertionError("Go oracle returned an unexpected result count")
    return results
