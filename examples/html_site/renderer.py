"""Load and render an associated directory of gotpl HTML templates."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from gotpl import Environment, HTMLTemplate


def load_template_directory(directory: str | Path) -> dict[str, str]:
    """Read every ``*.gotpl`` file under a directory as a named source."""

    root = Path(directory)
    if not root.is_dir():
        raise ValueError(f"template path {root} must be a directory")
    sources = {
        path.relative_to(root).as_posix(): path.read_text(encoding="utf-8")
        for path in sorted(root.rglob("*.gotpl"))
        if path.is_file()
    }
    if not sources:
        raise ValueError(f"template directory {root} contains no *.gotpl files")
    return sources


@dataclass(frozen=True, slots=True)
class SiteRenderer:
    """A reusable, contextually escaped HTML template association."""

    template: HTMLTemplate

    @classmethod
    def from_directory(cls, directory: str | Path) -> SiteRenderer:
        """Load and compile one complete template directory."""

        sources = load_template_directory(directory)
        return cls(Environment().from_html_sources(sources))

    def render_page(self, name: str, context: object) -> str:
        """Render one page while sharing all partial definitions."""

        return self.template.render_template(name, context)

    def render_pages(self, contexts: Mapping[str, object]) -> dict[str, str]:
        """Render several pages from the same compiled association."""

        return {
            name: self.render_page(name, context) for name, context in contexts.items()
        }


__all__ = ["SiteRenderer", "load_template_directory"]
