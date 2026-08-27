from collections.abc import Callable

import pytest

import gotpl.funcs.sprig as sprig


def function(name: str) -> Callable[..., object]:
    return sprig.generic_func_map()[name]


@pytest.mark.parametrize("message", ["", "requested Ω failure"])
def test_fail_preserves_empty_and_unicode_messages(message: str) -> None:
    with pytest.raises(RuntimeError) as raised:
        function("fail")(message)

    assert str(raised.value) == message
