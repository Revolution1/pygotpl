"""Sprig-compatible semantic versions and constraints."""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import total_ordering

from gotpl.runtime import FunctionResult

_VERSION_RE = re.compile(
    r"^v?(?P<major>[0-9]+)"
    r"(?:\.(?P<minor>[0-9]+))?"
    r"(?:\.(?P<patch>[0-9]+))?"
    r"(?:-(?P<prerelease>[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?"
    r"(?:\+(?P<metadata>[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?$"
)
_COMPARATOR_RE = re.compile(
    r"(?P<operator>>=|=>|<=|=<|!=|~>|\^|~|>|<|=)?\s*"
    r"(?P<version>v?[0-9xX*]+(?:\.[0-9xX*]+){0,2}"
    r"(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?)"
)
_UINT64_MAX = (1 << 64) - 1


@total_ordering
@dataclass(frozen=True, slots=True)
class Version:
    """A semantic version exposing the method names used by Go templates."""

    Major: int
    Minor: int
    Patch: int
    _prerelease: str = ""
    _metadata: str = ""
    _original: str = ""

    def Prerelease(self) -> str:
        return self._prerelease

    def Metadata(self) -> str:
        return self._metadata

    def Original(self) -> str:
        return self._original

    def Compare(self, other: Version) -> int:
        if self < other:
            return -1
        if self > other:
            return 1
        return 0

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Version):
            return NotImplemented
        return self._precedence_key() == other._precedence_key()

    def __lt__(self, other: Version) -> bool:
        core = (self.Major, self.Minor, self.Patch)
        other_core = (other.Major, other.Minor, other.Patch)
        if core != other_core:
            return core < other_core
        return _compare_prerelease(self._prerelease, other._prerelease) < 0

    def __hash__(self) -> int:
        return hash(self._precedence_key())

    def __str__(self) -> str:
        value = f"{self.Major}.{self.Minor}.{self.Patch}"
        if self._prerelease:
            value += f"-{self._prerelease}"
        if self._metadata:
            value += f"+{self._metadata}"
        return value

    def _precedence_key(self) -> tuple[int, int, int, str]:
        return self.Major, self.Minor, self.Patch, self._prerelease


def semver(value: str) -> Version:
    """Parse the relaxed semantic-version syntax accepted by Sprig."""

    match = _VERSION_RE.fullmatch(value)
    if match is None:
        raise ValueError("Invalid Semantic Version")
    prerelease = match.group("prerelease") or ""
    _validate_prerelease(prerelease)
    segments = [
        int(match.group("major")),
        int(match.group("minor") or 0),
        int(match.group("patch") or 0),
    ]
    if any(segment > _UINT64_MAX for segment in segments):
        raise ValueError("Error parsing version segment: value out of range")
    return Version(
        segments[0],
        segments[1],
        segments[2],
        prerelease,
        match.group("metadata") or "",
        value,
    )


def semver_compare(constraint: str, value: str) -> bool:
    """Return whether a version satisfies a Masterminds-style constraint."""

    version = semver(value)
    groups = [part.strip() for part in constraint.split("||")]
    if not groups or any(not group for group in groups):
        raise ValueError("improper constraint")
    return any(_check_group(group, version) for group in groups)


def semver_result(value: str) -> FunctionResult:
    """Expose Sprig's version/error return pair to registered Python callers."""

    try:
        return FunctionResult.success(semver(value))
    except Exception as error:
        return FunctionResult.failure(error)


def semver_compare_result(constraint: str, value: str) -> FunctionResult:
    """Expose Sprig's boolean/error return pair to registered Python callers."""

    try:
        return FunctionResult.success(semver_compare(constraint, value))
    except Exception as error:
        return FunctionResult.failure(error)


def _check_group(group: str, version: Version) -> bool:
    hyphen = re.fullmatch(r"\s*(\S+)\s+-\s+(\S+)\s*", group)
    if hyphen is not None:
        lower = semver(hyphen.group(1))
        upper_text = hyphen.group(2)
        upper, specified = _parse_partial(upper_text)
        if specified < 3:
            upper = _wildcard_upper(upper, specified)
            return version >= lower and _below_exclusive_core(version, upper)
        return version >= lower and version <= upper

    matches = list(_COMPARATOR_RE.finditer(group))
    residue = _COMPARATOR_RE.sub("", group).replace(",", "").strip()
    if not matches or residue:
        raise ValueError("improper constraint")
    allows_prerelease = any("-" in match.group("version") for match in matches)
    if version.Prerelease() and not allows_prerelease:
        return False
    return all(
        _check_comparator(
            match.group("operator") or "=", match.group("version"), version
        )
        for match in matches
    )


def _check_comparator(operator: str, target_text: str, version: Version) -> bool:
    operator = {"=>": ">=", "=<": "<=", "~>": "~"}.get(operator, operator)
    target, specified = _parse_partial(target_text)
    wildcard = any(part.lower() in {"x", "*"} for part in _core_parts(target_text))
    if wildcard:
        if operator not in {"=", "!="}:
            raise ValueError("improper constraint")
        if specified == 0:
            return operator == "="
        lower_ok = version >= target
        upper_ok = _below_exclusive_core(version, _wildcard_upper(target, specified))
        return (lower_ok and upper_ok) is (operator == "=")
    if operator == "^":
        if specified == 1 or target.Major > 0:
            upper = Version(target.Major + 1, 0, 0)
        elif specified == 2 or target.Minor > 0:
            upper = Version(0, target.Minor + 1, 0)
        else:
            upper = Version(0, 0, target.Patch + 1)
        return target <= version and _below_exclusive_core(version, upper)
    if operator == "~":
        upper = (
            Version(target.Major + 1, 0, 0)
            if specified == 1
            else Version(target.Major, target.Minor + 1, 0)
        )
        return target <= version and _below_exclusive_core(version, upper)
    if specified < 3 and not target.Prerelease():
        upper = _wildcard_upper(target, specified)
        if operator == "=":
            return target <= version and _below_exclusive_core(version, upper)
        if operator == "!=":
            return not (target <= version and _below_exclusive_core(version, upper))
        if operator == ">":
            return version >= upper
        if operator == "<=":
            return _below_exclusive_core(version, upper)
    comparisons = {
        "=": version == target,
        "!=": version != target,
        ">": version > target,
        ">=": version >= target,
        "<": version < target,
        "<=": version <= target,
    }
    return comparisons[operator]


def _parse_partial(value: str) -> tuple[Version, int]:
    core = value.removeprefix("v").split("-", 1)[0].split("+", 1)[0]
    parts = core.split(".")
    specified = next(
        (index for index, part in enumerate(parts) if part.lower() in {"x", "*"}),
        len(parts),
    )
    normalized = ["0" if part.lower() in {"x", "*"} else part for part in parts]
    suffix = value[len(core) + (1 if value.startswith("v") else 0) :]
    return semver(".".join(normalized) + suffix), specified


def _core_parts(value: str) -> list[str]:
    return value.removeprefix("v").split("-", 1)[0].split("+", 1)[0].split(".")


def _wildcard_upper(version: Version, specified: int) -> Version:
    if specified <= 1:
        return Version(version.Major + 1, 0, 0)
    return Version(version.Major, version.Minor + 1, 0)


def _below_exclusive_core(version: Version, upper: Version) -> bool:
    return (version.Major, version.Minor, version.Patch) < (
        upper.Major,
        upper.Minor,
        upper.Patch,
    )


def _validate_prerelease(value: str) -> None:
    for identifier in value.split(".") if value else ():
        if identifier.isdigit() and len(identifier) > 1 and identifier.startswith("0"):
            raise ValueError("Invalid Semantic Version")


def _compare_prerelease(left: str, right: str) -> int:
    if left == right:
        return 0
    if not left:
        return 1
    if not right:
        return -1
    for left_part, right_part in zip(left.split("."), right.split("."), strict=False):
        if left_part == right_part:
            continue
        left_numeric = left_part.isdigit()
        right_numeric = right_part.isdigit()
        if left_numeric and right_numeric:
            return -1 if int(left_part) < int(right_part) else 1
        if left_numeric != right_numeric:
            return -1 if left_numeric else 1
        return -1 if left_part < right_part else 1
    return -1 if len(left.split(".")) < len(right.split(".")) else 1
