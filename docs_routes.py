from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import markdown
from flask import Blueprint, render_template


_ROOT = Path(__file__).resolve().parent
DOCS_DIR = (_ROOT / "docs") if (_ROOT / "docs").exists() else (_ROOT / "DOCS")
docs_bp = Blueprint("docs", __name__)


def _slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", str(value or "").strip().lower()).strip("-") or "section"


def _render_markdown(text: str) -> str:
    return markdown.markdown(
        str(text or ""),
        extensions=["fenced_code", "tables", "toc", "nl2br", "sane_lists"],
        output_format="html5",
    )


def _section_title(text: str, fallback: str) -> str:
    match = re.search(r"^#\s+(.+)$", text, re.M)
    return match.group(1).strip() if match else fallback


def load_docs_sections() -> list[dict[str, Any]]:
    sections: list[dict[str, Any]] = []
    for path in sorted(DOCS_DIR.glob("*.md")):
        raw = path.read_text(encoding="utf-8")
        title = _section_title(raw, path.stem.replace("-", " ").title())
        sections.append(
            {
                "title": title,
                "slug": _slugify(title),
                "html": _render_markdown(raw),
                "source": str(path.name),
            }
        )
    return sections


@docs_bp.route("/docs")
def docs_page():
    return render_template("docs.html", sections=load_docs_sections())
