import base64
import re
from uuid import UUID

import pytest

import gotpl
import gotpl.funcs.sprig as sprig
from gotpl.funcs.sprig import environment, network, randoms


def repeated_byte(value: int) -> randoms.Entropy:
    return lambda count: bytes([value]) * count


def test_random_string_families_use_injectable_crypto_entropy() -> None:
    assert randoms.rand_alpha_numeric(4, entropy=repeated_byte(33)) == "AAAA"
    assert randoms.rand_alpha(4, entropy=repeated_byte(33)) == "AAAA"
    assert randoms.rand_ascii(4, entropy=repeated_byte(0)) == "    "
    assert randoms.rand_numeric(4, entropy=repeated_byte(16)) == "0000"
    assert randoms.rand_alpha(-1, entropy=repeated_byte(33)) == ""


def test_crypto_entropy_rejection_and_invalid_source_lengths() -> None:
    chunks = iter((b"\x7f", b"\x21"))

    assert randoms.rand_alpha(1, entropy=lambda _count: next(chunks)) == "A"
    with pytest.raises(ValueError, match="wrong byte count"):
        randoms.rand_alpha(1, entropy=lambda _count: b"")


def test_random_bytes_and_uuid_use_injected_entropy() -> None:
    assert randoms.rand_bytes(3, entropy=lambda count: b"abc"[:count]) == "YWJj"
    assert randoms.uuid_v4(entropy=lambda count: bytes(count)) == (
        "00000000-0000-4000-8000-000000000000"
    )
    with pytest.raises(ValueError, match="wrong byte count"):
        randoms.uuid_v4(entropy=lambda _count: b"short")


def test_registered_random_bytes_preserves_go_value_error_contract() -> None:
    success = sprig.generic_func_map(entropy=lambda count: bytes(count))["randBytes"](3)
    failure = sprig.generic_func_map(entropy=lambda _count: b"short")["randBytes"](3)

    assert success == gotpl.FunctionResult.success("AAAA")
    assert isinstance(failure, gotpl.FunctionResult)
    assert isinstance(failure.error, ValueError)
    with pytest.raises(ValueError, match="negative"):
        sprig.generic_func_map()["randBytes"](-1)


def test_default_random_outputs_have_the_required_shapes() -> None:
    assert re.fullmatch(r"[A-Za-z0-9]{24}", randoms.rand_alpha_numeric(24))
    assert re.fullmatch(r"[A-Za-z]{24}", randoms.rand_alpha(24))
    assert re.fullmatch(r"[0-9]{24}", randoms.rand_numeric(24))
    assert len(randoms.rand_ascii(24)) == 24
    assert len(base64.b64decode(randoms.rand_bytes(12))) == 12
    assert UUID(randoms.uuid_v4()).version == 4


def test_pseudo_random_helpers_accept_an_injected_index_source() -> None:
    assert randoms.rand_int(10, 20, randbelow=lambda width: width - 1) == 19
    assert randoms.shuffle("abcd", randbelow=lambda _width: 0) == "bcda"
    assert randoms.shuffle("abcd", randbelow=lambda width: width - 1) == "abcd"
    assert randoms.shuffle("", randbelow=lambda _width: 0) == ""
    with pytest.raises(ValueError):
        randoms.rand_int(3, 3)
    with pytest.raises(ValueError):
        randoms.rand_int(-(1 << 63), (1 << 63) - 1)


def test_shuffle_operates_on_unicode_code_points_like_go_runes() -> None:
    assert randoms.shuffle("A😀界", randbelow=lambda _width: 0) == "😀界A"


def test_environment_expansion_matches_go_shell_name_rules() -> None:
    values = {"FOO": "bar", "9": "nine", "strange-name": "value"}

    assert environment.env("FOO", environ=values) == "bar"
    assert environment.env("MISSING", environ=values) == ""
    assert (
        environment.expand_env(
            "$FOO/${FOO}/$MISSING/$/$9/${9}/${}/${strange-name}/x${UNCLOSED",
            environ=values,
        )
        == "bar/bar//$/nine/nine//value/xUNCLOSED"
    )


def test_dns_selection_is_injectable_and_empty_results_fail(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def resolver(_name: str) -> list[str]:
        return ["192.0.2.1", "192.0.2.2"]

    assert (
        network.get_host_by_name(
            "example.test", resolver=resolver, randbelow=lambda _width: 1
        )
        == "192.0.2.2"
    )

    def fake_lookup(_name: str) -> tuple[str, list[str], list[str]]:
        return "example.test", [], ["192.0.2.3"]

    monkeypatch.setattr(
        network.socket,
        "gethostbyname_ex",
        fake_lookup,
    )
    assert (
        network.get_host_by_name("example.test", randbelow=lambda _width: 0)
        == "192.0.2.3"
    )
    with pytest.raises(ValueError):
        network.get_host_by_name(
            "empty.test", resolver=lambda _name: [], randbelow=lambda width: width - 1
        )


def test_registry_injects_external_state_without_changing_hermetic_membership() -> None:
    functions = sprig.text_func_map(
        entropy=repeated_byte(33),
        randbelow=lambda _width: 0,
        environ={"NAME": "Ada"},
        resolver=lambda _name: ["192.0.2.10"],
    )

    assert (
        gotpl.render(
            '{{randAlpha 3}}/{{randInt 4 5}}/{{env "NAME"}}/'
            '{{getHostByName "example.test"}}/{{shuffle "abc"}}',
            functions=functions,
        )
        == "AAA/4/Ada/192.0.2.10/bca"
    )

    hermetic = sprig.hermetic_text_func_map(
        entropy=repeated_byte(33), randbelow=lambda _width: 0
    )
    assert "randInt" in hermetic
    assert "shuffle" in hermetic
    assert "randAlpha" not in hermetic
    assert "env" not in hermetic
    assert "getHostByName" not in hermetic
