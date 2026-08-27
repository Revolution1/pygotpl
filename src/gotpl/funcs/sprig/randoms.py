"""Sprig-compatible random helpers with injectable randomness."""

from __future__ import annotations

import base64
import os
import random
from collections.abc import Callable
from uuid import UUID

from gotpl.runtime import FunctionResult

Entropy = Callable[[int], bytes]
RandBelow = Callable[[int], int]


def rand_alpha_numeric(count: int, *, entropy: Entropy | None = None) -> str:
    return _random_string(count, 32, 123, True, True, entropy or os.urandom)


def rand_alpha(count: int, *, entropy: Entropy | None = None) -> str:
    return _random_string(count, 32, 123, True, False, entropy or os.urandom)


def rand_ascii(count: int, *, entropy: Entropy | None = None) -> str:
    return _random_string(count, 32, 127, False, False, entropy or os.urandom)


def rand_numeric(count: int, *, entropy: Entropy | None = None) -> str:
    return _random_string(count, 32, 123, False, True, entropy or os.urandom)


def rand_bytes(count: int, *, entropy: Entropy | None = None) -> str:
    if count < 0:
        raise ValueError("negative random byte count")
    source = entropy or os.urandom
    value = source(count)
    if len(value) != count:
        raise ValueError("entropy source returned the wrong byte count")
    return base64.b64encode(value).decode("ascii")


def rand_bytes_result(count: int, *, entropy: Entropy | None = None) -> FunctionResult:
    """Expose randBytes' Go value/error pair while retaining allocation panics."""

    if count < 0:
        return FunctionResult.success(rand_bytes(count, entropy=entropy))
    try:
        return FunctionResult.success(rand_bytes(count, entropy=entropy))
    except Exception as error:
        return FunctionResult.failure(error, "")


def uuid_v4(*, entropy: Entropy | None = None) -> str:
    source = entropy or os.urandom
    value = bytearray(source(16))
    if len(value) != 16:
        raise ValueError("entropy source returned the wrong byte count")
    value[6] = (value[6] & 0x0F) | 0x40
    value[8] = (value[8] & 0x3F) | 0x80
    return str(UUID(bytes=bytes(value)))


def rand_int(minimum: int, maximum: int, *, randbelow: RandBelow | None = None) -> int:
    width = ((maximum - minimum + (1 << 63)) % (1 << 64)) - (1 << 63)
    chooser = randbelow or random.randrange
    return minimum + chooser(width)


def shuffle(value: str, *, randbelow: RandBelow | None = None) -> str:
    if not value:
        return value
    chooser = randbelow or random.randrange
    characters = list(value)
    for index in range(len(characters) - 1, 0, -1):
        chosen = chooser(index + 1)
        if chosen != index:
            characters[index], characters[chosen] = (
                characters[chosen],
                characters[index],
            )
    return "".join(characters)


def _random_string(
    count: int,
    start: int,
    end: int,
    letters: bool,
    numbers: bool,
    entropy: Entropy,
) -> str:
    if count <= 0:
        return ""
    result = [""] * count
    position = count - 1
    gap = end - start
    while position >= 0:
        character = chr(start + _crypto_randbelow(gap, entropy))
        if (
            (letters and character.isalpha())
            or (numbers and character.isdigit())
            or (not letters and not numbers)
        ):
            result[position] = character
            position -= 1
    return "".join(result)


def _crypto_randbelow(bound: int, entropy: Entropy) -> int:
    bits = bound.bit_length()
    byte_count = (bits + 7) // 8
    mask = (1 << bits) - 1
    while True:
        chunk = entropy(byte_count)
        if len(chunk) != byte_count:
            raise ValueError("entropy source returned the wrong byte count")
        candidate = int.from_bytes(chunk, "big") & mask
        if candidate < bound:
            return candidate
