from __future__ import annotations

from pathlib import Path

import pytest

from examples.html_site import SiteRenderer, load_template_directory
from examples.html_site.__main__ import example_page_contexts, main

TEMPLATES = Path(__file__).parents[2] / "examples" / "html_site" / "templates"


def test_template_directory_contains_partials_and_pages() -> None:
    assert set(load_template_directory(TEMPLATES)) == {
        "pages/article.html.gotpl",
        "pages/home.html.gotpl",
        "partials/footer.html.gotpl",
        "partials/header.html.gotpl",
    }


def test_renderer_reuses_partials_and_contextually_escapes_pages() -> None:
    renderer = SiteRenderer.from_directory(TEMPLATES)
    rendered = renderer.render_pages(example_page_contexts())

    home = rendered["pages/home.html.gotpl"]
    assert "<title>Home · gotpl Journal</title>" in home
    assert '<a class="brand" href="/home.html">gotpl Journal</a>' in home
    assert "What this example demonstrates" in home
    assert "rendered with gotpl" in home

    article = rendered["pages/article.html.gotpl"]
    assert "&lt;script&gt;alert(&#39;unsafe&#39;)&lt;/script&gt;" in article
    assert 'href="/home.html?from=article&amp;format=html"' in article
    assert "<script>alert" not in article


def test_loader_rejects_missing_and_empty_directories(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="must be a directory"):
        load_template_directory(tmp_path / "missing")
    with pytest.raises(ValueError, match=r"contains no \*\.gotpl files"):
        load_template_directory(tmp_path)


def test_cli_writes_both_pages(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    output = tmp_path / "site"

    assert main(["--templates", str(TEMPLATES), "--output", str(output)]) == 0
    assert (output / "home.html").is_file()
    assert (output / "article.html").is_file()
    assert capsys.readouterr().out.splitlines() == [
        str(output / "home.html"),
        str(output / "article.html"),
    ]


def test_cli_reports_loader_errors(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert (
        main(
            [
                "--templates",
                str(tmp_path / "missing"),
                "--output",
                str(tmp_path / "out"),
            ]
        )
        == 1
    )
    assert "Error: template path" in capsys.readouterr().out
