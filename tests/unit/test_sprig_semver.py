import pytest

import gotpl
import gotpl.funcs.sprig as sprig
from gotpl.funcs.sprig.semver import Version, semver, semver_compare


def test_semver_exposes_sprig_version_methods_and_normalized_text() -> None:
    version = semver("v1.2.3-beta.1+build.5")

    assert (version.Major, version.Minor, version.Patch) == (1, 2, 3)
    assert version.Prerelease() == "beta.1"
    assert version.Metadata() == "build.5"
    assert version.Original() == "v1.2.3-beta.1+build.5"
    assert str(version) == "1.2.3-beta.1+build.5"
    assert str(semver("2")) == "2.0.0"
    assert str(semver("2.4")) == "2.4.0"
    assert str(semver("01.02.003")) == "1.2.3"
    assert semver("01.02.003").Original() == "01.02.003"
    assert str(semver("18446744073709551615.0.0")) == ("18446744073709551615.0.0")


def test_semver_precedence_and_compare_ignore_build_metadata() -> None:
    ordered = [
        "1.0.0-alpha",
        "1.0.0-alpha.1",
        "1.0.0-alpha.beta",
        "1.0.0-beta",
        "1.0.0-beta.2",
        "1.0.0-beta.11",
        "1.0.0-rc.1",
        "1.0.0",
    ]
    versions = [semver(value) for value in ordered]

    assert versions == sorted(reversed(versions))
    assert semver("1.0.0+one") == semver("1.0.0+two")
    assert hash(semver("1.0.0+one")) == hash(semver("1.0.0+two"))
    assert not semver("1.0.0") < semver("1.0.0-rc.1")
    assert semver("1.0.0").Compare(semver("1.0.1")) == -1
    assert semver("1.0.1").Compare(semver("1.0.0")) == 1
    assert semver("1.0.0+one").Compare(semver("1.0.0+two")) == 0
    assert semver("1.0.0") != object()


@pytest.mark.parametrize(
    "value",
    [
        "",
        "not-a-version",
        "V1.2.3",
        " 1.2.3 ",
        "1.2.3-beta.01",
    ],
)
def test_semver_rejects_invalid_versions(value: str) -> None:
    with pytest.raises(ValueError, match="Invalid Semantic Version"):
        semver(value)


def test_semver_rejects_uint64_segment_overflow() -> None:
    with pytest.raises(ValueError, match="Error parsing version segment"):
        semver("18446744073709551616.0.0")


@pytest.mark.parametrize(
    ("constraint", "value", "expected"),
    [
        ("*", "99.2.1", True),
        ("!=*", "99.2.1", False),
        ("1.x", "1.9.9", True),
        ("1.2.x", "1.3.0", False),
        ("1.2", "1.2.8", True),
        ("^2.3.4", "2.9.0", True),
        ("^0.3.4", "0.4.0", False),
        ("^0.0.4", "0.0.5", False),
        ("~2", "2.9.0", True),
        ("~2.3", "2.4.0", False),
        ("1.2 - 2.3", "2.3.99", True),
        ("1.2.0 - 2.3.0", "2.3.1", False),
        (">1.0.0 <=2.0.0", "2.0.0", True),
        ("<1.0.0 || >=2.0.0", "1.5.0", False),
        ("!=1.2.3", "1.2.4", True),
        ("=1.2.3", "1.2.3+meta", True),
        (">=1.2.3", "1.3.0-beta.1", False),
        (">=1.2.3-0", "1.3.0-beta.1", True),
        ("=>1.2.3", "2.0.0", True),
        ("=<2.0.0", "1.2.3", True),
        ("~>1.2.3", "1.2.9", True),
        ("!=4.1", "4.1.1", False),
        (">11", "11.9.9", False),
        ("<=11", "11.9.9", True),
        ("^0", "0.2.3", True),
        ("^0.0", "0.0.3", True),
    ],
)
def test_semver_constraints(constraint: str, value: str, expected: bool) -> None:
    assert semver_compare(constraint, value) is expected


@pytest.mark.parametrize("constraint", ["", "|| 1.2.3", "not a constraint", ">1.x"])
def test_semver_rejects_invalid_constraints(constraint: str) -> None:
    with pytest.raises(ValueError, match="improper constraint"):
        semver_compare(constraint, "1.2.3")


def test_version_constructor_supports_internal_constraint_bounds() -> None:
    assert Version(1, 2, 3) < Version(2, 0, 0)


def test_registered_semver_functions_expose_go_style_results() -> None:
    functions = sprig.generic_func_map()
    parsed = functions["semver"]("1.2.3")
    compared = functions["semverCompare"]("^1", "1.9.0")
    invalid_version = functions["semver"]("invalid")
    invalid_constraint = functions["semverCompare"]("||", "1.2.3")

    assert isinstance(parsed, gotpl.FunctionResult)
    assert str(parsed.value) == "1.2.3"
    assert compared == gotpl.FunctionResult.success(True)
    assert isinstance(invalid_version, gotpl.FunctionResult)
    assert isinstance(invalid_version.error, ValueError)
    assert isinstance(invalid_constraint, gotpl.FunctionResult)
    assert isinstance(invalid_constraint.error, ValueError)
