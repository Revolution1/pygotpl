"""Construction of isolated Slim-Sprig v3.0.0 registry profiles."""

from collections.abc import Callable, Mapping

from gotpl.funcs.sprig import generic_func_map as sprig_generic_func_map
from gotpl.funcs.sprig.dates import Clock
from gotpl.funcs.sprig.network import Resolver
from gotpl.funcs.sprig.randoms import RandBelow

from . import numeric

_SPRIG_ONLY_NAMES = frozenset(
    {
        "abbrev",
        "abbrevboth",
        "add1f",
        "addf",
        "bcrypt",
        "buildCustomCert",
        "camelcase",
        "decryptAES",
        "deepCopy",
        "derivePassword",
        "divf",
        "encryptAES",
        "genCA",
        "genCAWithKey",
        "genPrivateKey",
        "genSelfSignedCert",
        "genSelfSignedCertWithKey",
        "genSignedCert",
        "genSignedCertWithKey",
        "htpasswd",
        "initials",
        "kebabcase",
        "merge",
        "mergeOverwrite",
        "mulf",
        "mustDeepCopy",
        "mustMerge",
        "mustMergeOverwrite",
        "mustPush",
        "nospace",
        "push",
        "randAlpha",
        "randAlphaNum",
        "randAscii",
        "randBytes",
        "randNumeric",
        "semver",
        "semverCompare",
        "sha512sum",
        "shuffle",
        "snakecase",
        "subf",
        "swapcase",
        "untitle",
        "uuidv4",
        "wrap",
        "wrapWith",
    }
)
_NONHERMETIC_NAMES = frozenset(
    {
        "date",
        "dateInZone",
        "dateModify",
        "date_in_zone",
        "date_modify",
        "env",
        "expandenv",
        "getHostByName",
        "htmlDate",
        "htmlDateInZone",
        "now",
    }
)


def generic_func_map(
    *,
    clock: Clock | None = None,
    randbelow: RandBelow | None = None,
    environ: Mapping[str, str] | None = None,
    resolver: Resolver | None = None,
) -> dict[str, Callable[..., object]]:
    """Return implemented functions belonging to Slim-Sprig v3.0.0."""

    functions = {
        name: function
        for name, function in sprig_generic_func_map(
            clock=clock, randbelow=randbelow, environ=environ, resolver=resolver
        ).items()
        if name not in _SPRIG_ONLY_NAMES
    }
    functions.update(
        {
            "add": numeric.add,
            "add1": numeric.add1,
            "biggest": numeric.maximum,
            "div": numeric.div,
            "int": numeric.to_int,
            "int64": numeric.to_int,
            "max": numeric.maximum,
            "min": numeric.minimum,
            "mod": numeric.mod,
            "mul": numeric.mul,
            "sub": numeric.sub,
        }
    )
    return functions


def text_func_map(
    *,
    clock: Clock | None = None,
    randbelow: RandBelow | None = None,
    environ: Mapping[str, str] | None = None,
    resolver: Resolver | None = None,
) -> dict[str, Callable[..., object]]:
    """Return a mutable Slim-Sprig text-template function map."""

    return generic_func_map(
        clock=clock, randbelow=randbelow, environ=environ, resolver=resolver
    )


def html_func_map(
    *,
    clock: Clock | None = None,
    randbelow: RandBelow | None = None,
    environ: Mapping[str, str] | None = None,
    resolver: Resolver | None = None,
) -> dict[str, Callable[..., object]]:
    """Return a mutable Slim-Sprig HTML-template function map."""

    return generic_func_map(
        clock=clock, randbelow=randbelow, environ=environ, resolver=resolver
    )


def hermetic_text_func_map(
    *, clock: Clock | None = None, randbelow: RandBelow | None = None
) -> dict[str, Callable[..., object]]:
    """Return deterministic implemented Slim-Sprig text functions."""

    return {
        name: function
        for name, function in generic_func_map(clock=clock, randbelow=randbelow).items()
        if name not in _NONHERMETIC_NAMES
    }


def hermetic_html_func_map(
    *, clock: Clock | None = None, randbelow: RandBelow | None = None
) -> dict[str, Callable[..., object]]:
    """Return deterministic implemented Slim-Sprig HTML functions."""

    return hermetic_text_func_map(clock=clock, randbelow=randbelow)
