from gotpl.errors import TemplateSyntaxError
from gotpl.parse import parse_template

from .support import TemplateRequest, run_go_oracle_many


def generated_sources() -> list[str]:
    terms = [
        ".",
        ".Field",
        "$",
        "true",
        "false",
        "nil",
        "0",
        "-1",
        "1.5",
        '"text"',
        "`raw`",
        "'x'",
        'printf "%v" .',
    ]
    sources: list[str] = []
    for term in terms:
        sources.extend(
            [
                f"{{{{{term}}}}}",
                f"{{{{ {term} }}}}",
                f"{{{{if {term}}}}}yes{{{{else}}}}no{{{{end}}}}",
                f"{{{{with {term}}}}}yes{{{{else}}}}no{{{{end}}}}",
                f"{{{{range {term}}}}}yes{{{{else}}}}no{{{{end}}}}",
                f'{{{{{term} | printf "%v"}}}}',
                f'{{{{printf "%v" ({term})}}}}',
            ]
        )
    sources.extend(
        [
            "{{}}",
            "{{| printf}}",
            "{{printf |}}",
            "{{printf ( )}}",
            "{{if .}}",
            "{{else}}",
            "{{end}}",
            "{{break}}",
            "{{continue}}",
            "{{. | 1}}",
            "{{. | true}}",
            "{{printf 1, 2}}",
            "{{printf 1`x`}}",
            "{{if .}}a{{else}}b{{else}}c{{end}}",
            "{{range .}}{{else}}{{break}}{{end}}",
            '{{template "item" .}}',
            '{{define "item"}}body{{end}}{{template "item" .}}',
            '{{block "item" .}}body{{end}}',
        ]
    )
    return sources


def test_generated_parser_matrix_matches_go() -> None:
    sources = generated_sources()
    requests: list[TemplateRequest] = [
        {
            "engine": "text",
            "name": f"generated-{index}",
            "template": source,
            "data": None,
            "function_profile": "none",
        }
        for index, source in enumerate(sources)
    ]

    go_results = run_go_oracle_many(requests)

    for source, go_result in zip(sources, go_results, strict=True):
        go_accepted = (
            go_result["error"] is None or go_result["error"]["phase"] != "parse"
        )
        try:
            parse_template(source)
        except TemplateSyntaxError:
            python_accepted = False
        else:
            python_accepted = True
        assert python_accepted is go_accepted, source
