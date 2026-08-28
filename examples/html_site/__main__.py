"""Build the bundled two-page HTML site."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

from gotpl import TemplateError

from .renderer import SiteRenderer

_DEFAULT_TEMPLATES = Path(__file__).with_name("templates")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="gotpl-html-site")
    parser.add_argument(
        "--templates",
        type=Path,
        default=_DEFAULT_TEMPLATES,
        help="template directory (default: bundled example templates)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="directory to receive home.html and article.html",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Render the example site and return a process exit code."""

    arguments = _parser().parse_args(argv)
    try:
        renderer = SiteRenderer.from_directory(arguments.templates)
        rendered = renderer.render_pages(example_page_contexts())
        arguments.output.mkdir(parents=True, exist_ok=True)
        for template_name, html in rendered.items():
            output_name = Path(template_name).name.removesuffix(".gotpl")
            destination = arguments.output / output_name
            destination.write_text(html, encoding="utf-8")
            print(destination)
    except (OSError, TemplateError, ValueError) as error:
        print(f"Error: {error}")
        return 1
    return 0


def example_page_contexts() -> dict[str, object]:
    """Return the data used to build the bundled home and article pages."""

    shared: dict[str, object] = {
        "SiteName": "gotpl Journal",
        "Year": 2026,
        "Navigation": [
            {"URL": "/home.html", "Label": "Home"},
            {"URL": "/article.html", "Label": "Article"},
        ],
    }
    return {
        "pages/home.html.gotpl": {
            **shared,
            "Title": "Home",
            "Heading": "HTML templates without Go",
            "Introduction": (
                "Load a directory once, reuse partials, and render safely."
            ),
            "Features": [
                "Reusable header and footer definitions",
                "Context-aware HTML, URL, CSS, and JavaScript escaping",
                "One immutable template association for every page",
            ],
        },
        "pages/article.html.gotpl": {
            **shared,
            "Title": "Contextual escaping",
            "Article": {
                "Title": "Why contextual escaping matters",
                "Summary": "The same value is treated differently by context.",
                "Body": (
                    "Caller content such as <script>alert('unsafe')</script> "
                    "is text, not trusted markup."
                ),
                "SourceURL": "/home.html?from=article&format=html",
            },
        },
    }


if __name__ == "__main__":
    raise SystemExit(main())
