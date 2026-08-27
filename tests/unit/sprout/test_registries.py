from __future__ import annotations

import pytest

from gotpl import Template
from gotpl.funcs.sprout import FunctionRegistry, Handler, group, registry


@pytest.mark.parametrize(
    ("registry_name", "source", "expected"),
    [
        (
            "backward",
            '{{urlJoin (urlParse "https://example.com/a?q=x")}}',
            "https://example.com/a?q=x",
        ),
        (
            "checksum",
            '{{sha1Sum "hello"}}|{{sha256sum "hello"}}|'
            '{{md5Sum "hello"}}|{{adler32Sum "hello"}}',
            "aaf4c61ddcc5e8a2dabede0f3b482cd9aea9434d|"
            "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824|"
            "5d41402abc4b2a76b9719d911017c592|103547413",
        ),
        (
            "filesystem",
            '{{pathBase "/a/b/"}}|{{pathDir "/a/b/"}}|'
            '{{pathExt "a.tar.gz"}}|{{pathClean "a//b/../c"}}|'
            '{{pathIsAbs "/a"}}',
            "b|/a/b|.gz|a/c|true",
        ),
        (
            "semver",
            '{{semverCompare ">=1.2.0 <2.0.0" "1.5.3"}}|'
            '{{semver "1.2.3-beta.1+build"}}',
            "true|1.2.3-beta.1+build",
        ),
        (
            "std",
            '{{hello}}|{{default "d" ""}}|{{empty 0}}|{{all 1 "x"}}|'
            '{{any 0 "x"}}|{{coalesce 0 "x"}}|'
            '{{ternary "yes" "no" true}}|{{cat "a" nil "b"}}',
            "Hello!|d|true|true|true|x|yes|a b",
        ),
    ],
)
def test_initial_registries_match_the_sprout_oracle(
    registry_name: str, source: str, expected: str
) -> None:
    functions = Handler(registry(registry_name)).build()
    assert Template(source, functions=functions).render() == expected


def test_handler_assigns_aliases_without_overwriting_earlier_functions() -> None:
    def custom_sha1(_value: object) -> str:
        return "custom"

    custom = FunctionRegistry(
        name="custom",
        uid="example.custom",
        functions={"sha1Sum": custom_sha1},
    )
    functions = Handler(custom, registry("checksum")).build()

    assert functions["sha1Sum"]("hello") == "custom"
    assert functions["sha1sum"]("hello") == "custom"
    with pytest.raises(TypeError):
        functions["new"] = lambda: None  # type: ignore[index]


def test_unknown_registry_is_explicit() -> None:
    with pytest.raises(KeyError, match="unknown Sprout registry"):
        registry("missing")


@pytest.mark.parametrize(("name", "count"), [("all", 251), ("hermetic", 227)])
def test_pinned_groups_build_the_exact_inventory(name: str, count: int) -> None:
    registry_group = group(name)
    functions = Handler(*registry_group.registries).build()

    assert len(functions) == count
    assert set(functions) == set(registry_group.function_names)


def test_handler_can_add_a_group_and_rejects_unknown_groups() -> None:
    handler = Handler()
    handler.add_group(group("hermetic"))

    assert "env" not in handler.build()
    with pytest.raises(KeyError, match="unknown Sprout group"):
        group("missing")


def test_environment_registry_uses_the_current_process_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PYGOTPL_SPROUT_TEST", "hello world")
    functions = Handler(registry("env")).build()
    source = '{{env "PYGOTPL_SPROUT_TEST"}}|{{expandEnv "$PYGOTPL_SPROUT_TEST/x"}}'

    assert Template(source, functions=functions).render() == "hello world|hello world/x"
