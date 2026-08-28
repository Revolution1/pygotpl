"""Exercise every public workspace distribution from built wheels."""

from __future__ import annotations

from importlib.metadata import distribution
from importlib.util import find_spec
from pathlib import Path
from shutil import which

import goduration
import gotime
from goduration.go import Duration as GoDuration
from goduration.python import Duration as PythonDuration
from gotime.go import Time as GoTime
from gotime.python import Time as PythonTime

import gotpl
from gotpl.funcs.helm import function_map
from gotpl.funcs.sprig import text_func_map


def _placeholder(*_arguments: object) -> str:
    return "placeholder"


def main() -> None:
    for executable in ("go", "cc", "gcc", "clang", "cl"):
        assert which(executable) is None, executable

    modules = (goduration, gotime, gotpl)
    for module in modules:
        module_file = module.__file__
        assert module_file is not None
        location = Path(module_file).resolve()
        assert "site-packages" in location.parts, location

    for name, expected_files in {
        "gotpl": {"LICENSE", "THIRD_PARTY_NOTICES.md"},
        "goduration": {"LICENSE"},
        "gotime-py": {"LICENSE"},
    }.items():
        installed = distribution(name)
        assert installed.metadata["License-Expression"] == "Apache-2.0"
        assert set(installed.metadata.get_all("License-File") or ()) == expected_files
        files = installed.files
        assert files is not None
        packaged: dict[str, Path] = {
            entry.name: Path(str(installed.locate_file(entry)))
            for entry in files
            if "licenses" in entry.parts and entry.name in expected_files
        }
        assert set(packaged) == expected_files
        apache = packaged["LICENSE"].read_text(encoding="utf-8")
        assert "3. Grant of Patent License." in apache
        if name == "gotpl":
            notices = packaged["THIRD_PARTY_NOTICES.md"].read_text(encoding="utf-8")
            assert "Copyright 2009 The Go Authors." in notices
            assert "Copyright (C) 2013-2020 Masterminds" in notices

    assert goduration.Duration is GoDuration
    assert PythonDuration(2**100).nanoseconds == 2**100
    assert GoTime.from_unix(0).unix() == 0
    assert PythonTime.from_timestamp(0).timestamp() == 0
    assert gotpl.render('{{printf "%v" .}}', True) == "true"
    assert gotpl.render('{{printf "%v" .}}', True, format_mode="python") == "True"
    assert (
        gotpl.Template(r'{{regexFind `\d+` "v12"}}', functions=text_func_map()).render()
        == "12"
    )
    assert gotpl.render("Hello, {{.Name}}!", {"Name": "wheel"}) == ("Hello, wheel!")
    assert gotpl.render_html("<p>{{.}}</p>", "<wheel>") == ("<p>&lt;wheel&gt;</p>")
    html = gotpl.HTMLTemplate.from_sources(
        {
            "page.html": '<a href="/?q={{template "value" .}}">open</a>',
            "value.html": '{{define "value"}}{{.}}{{end}}',
        }
    )
    assert html.render("a&b") == '<a href="/?q=a%26b">open</a>'
    sandbox = gotpl.SandboxPolicy.strict(allow_functions={"reMatch"})
    engine = gotpl.TemplateEngine.from_sources(
        {"main.txt": '{{reMatch "wheel" .}}'},
        sandbox=sandbox,
        extensions=gotpl.PythonExtensions(re_match=True),
    )
    assert engine.render({"main.txt": "wheel"}) == {"main.txt": "true"}
    assert gotpl.ExecutionBudget.strict().max_template_depth == 100
    assert find_spec("yaml") is None
    assert find_spec("tomli_w") is None
    helm_functions = function_map(
        include=_placeholder,
        tpl=_placeholder,
        required=_placeholder,
        fail=_placeholder,
    )
    assert len(helm_functions) == 222


if __name__ == "__main__":
    main()
