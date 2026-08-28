from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from gotpl import (
    PythonExtensions,
    SandboxPolicy,
    SandboxViolationError,
    Template,
    TemplateExecutionError,
    TemplateSyntaxError,
)
from gotpl.funcs.helm import function_map as helm_function_map
from gotpl.funcs.slim_sprig import text_func_map as slim_sprig_text_func_map
from gotpl.funcs.sprig import text_func_map
from gotpl.funcs.sprout import Handler, group
from gotpl.pythonic.regex import (
    _compile_pattern,  # pyright: ignore[reportPrivateUsage]
)


def _late(*_arguments: object) -> str:
    return ""


def test_python_re_match_is_explicit_and_uses_search_semantics() -> None:
    with pytest.raises(TemplateSyntaxError, match="function 'reMatch' not defined"):
        Template('{{reMatch "x" "x"}}')

    extensions = PythonExtensions(re_match=True)
    template = Template(
        '{{reMatch `(?<=v)\\d+` "v12"}}|{{reMatch `^12` "v12"}}',
        extensions=extensions,
    )
    assert template.render() == "true|false"


def test_python_re_match_cache_is_bounded_and_invalid_patterns_are_actionable() -> None:
    _compile_pattern.cache_clear()
    extensions = PythonExtensions(re_match=True)
    for index in range(300):
        Template(
            '{{reMatch .pattern "value"}}',
            extensions=extensions,
        ).render({"pattern": f"value(?:{index})?"})

    assert _compile_pattern.cache_info().maxsize == 256
    assert _compile_pattern.cache_info().currsize == 256
    with pytest.raises(TemplateExecutionError, match="unterminated"):
        Template('{{reMatch "(" "value"}}', extensions=extensions).render()


def test_python_extensions_are_immutable_and_reject_function_collisions() -> None:
    extensions = PythonExtensions(re_match=True)
    with pytest.raises(FrozenInstanceError):
        extensions.re_match = False  # type: ignore[misc]
    with pytest.raises(ValueError, match=r"extension function collision.*reMatch"):
        Template(
            "ok",
            functions={"reMatch": lambda *_arguments: False},
            extensions=extensions,
        )


def test_re_match_requires_an_explicit_strict_sandbox_grant() -> None:
    extensions = PythonExtensions(re_match=True)
    with pytest.raises(SandboxViolationError, match=r"registered functions.*reMatch"):
        Template(
            '{{reMatch "x" "x"}}',
            extensions=extensions,
            sandbox=SandboxPolicy.strict(),
        )

    template = Template(
        '{{reMatch "x" "x"}}',
        extensions=extensions,
        sandbox=SandboxPolicy.strict(allow_functions={"reMatch"}),
    )
    assert template.render() == "true"


def test_re_match_does_not_leak_into_compatibility_or_ecosystem_maps() -> None:
    registries = (
        text_func_map(),
        slim_sprig_text_func_map(),
        Handler(*group("all").registries).build(),
        helm_function_map(
            include=_late,
            tpl=_late,
            required=_late,
            fail=_late,
        ),
    )

    assert all("reMatch" not in functions for functions in registries)


def test_python_extension_categories_can_be_selected_independently() -> None:
    extensions = PythonExtensions.from_categories("hashing", "compression")

    assert set(extensions.function_map()) == {
        "bz2Compress",
        "bz2Decompress",
        "gzipCompress",
        "gzipDecompress",
        "hashDigest",
        "md5",
        "sha1",
        "sha256",
        "sha512",
        "zlibCompress",
        "zlibDecompress",
        "lzmaCompress",
        "lzmaDecompress",
    }
    with pytest.raises(TemplateSyntaxError, match="function 'reMatch' not defined"):
        Template('{{reMatch "x" "x"}}', extensions=extensions)


def test_python_extension_all_and_common_profiles_are_convenient() -> None:
    common = PythonExtensions.common().function_map()
    all_functions = PythonExtensions.all().function_map()

    assert {"pyPrint", "pformat", "b64encode", "sha256", "gzipCompress"} <= set(common)
    assert "reMatch" not in common
    assert set(all_functions) == {*common, "reMatch"}


def test_python_text_encoding_hashing_and_compression_functions_compose() -> None:
    extensions = PythonExtensions.all()
    source = "|".join(
        (
            '{{pyPrint "release" 42}}',
            "{{pformat .mapping}}",
            '{{sha256 "hello"}}',
            '{{hashDigest "sha256" "hello"}}',
            '{{utf8Decode (b64decode (b64encode (utf8Encode "hello")))}}',
            '{{utf8Decode (gzipDecompress (gzipCompress (utf8Encode "hello")))}}',
            '{{utf8Decode (zlibDecompress (zlibCompress (utf8Encode "hello")))}}',
            '{{utf8Decode (bz2Decompress (bz2Compress (utf8Encode "hello")))}}',
            '{{utf8Decode (lzmaDecompress (lzmaCompress (utf8Encode "hello")))}}',
            '{{hexDecode (hexEncode (utf8Encode "hello")) | utf8Decode}}',
        )
    )

    rendered = Template(source, extensions=extensions).render(
        {"mapping": {"first": 1, "second": 2}}
    )

    digest = "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"
    assert rendered == (
        "release 42|{'first': 1, 'second': 2}|"
        f"{digest}|{digest}|hello|hello|hello|hello|hello|hello"
    )


def test_python_extension_category_errors_are_actionable() -> None:
    with pytest.raises(ValueError, match=r"unknown Python extension category.*archive"):
        PythonExtensions.from_categories("archive")  # type: ignore[arg-type]
