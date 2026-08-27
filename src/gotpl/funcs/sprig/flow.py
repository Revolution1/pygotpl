"""Sprig explicit flow-control helpers."""


def fail(message: str) -> str:
    raise RuntimeError(message)
