"""
Lightweight templating utility with optional Jinja2 support.

Usage:
    render_template("Hello {{name}}", {"name": "World"}) -> "Hello World"

This module first tries to use Jinja2 if available for robust features.
If Jinja2 is not installed, it falls back to a tiny, safe renderer that
replaces double-curly placeholders with their stringified values.
"""

from __future__ import annotations

from typing import Any, Mapping
import re


_JINJA_AVAILABLE = False
try:
    from jinja2 import Environment, StrictUndefined

    _JINJA_AVAILABLE = True
except Exception:
    _JINJA_AVAILABLE = False


def _render_with_fallback(template: str, context: Mapping[str, Any]) -> str:
    """Very small and safe fallback renderer.

    Only supports simple {{var}} replacements. Missing keys become empty strings.
    Whitespace inside braces is ignored, e.g. {{  key  }} works.
    """
    if not isinstance(template, str):
        return str(template)

    pattern = re.compile(r"\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\}\}")

    def _replace(match: re.Match[str]) -> str:
        key = match.group(1)
        value = context.get(key, "") if isinstance(context, Mapping) else ""
        return "" if value is None else str(value)

    return pattern.sub(_replace, template)


def render_template(template: str, context: Mapping[str, Any]) -> str:
    """Render a template string with the provided context.

    Prefers Jinja2 (if installed). Falls back to a tiny renderer otherwise.
    """
    if _JINJA_AVAILABLE:
        env = Environment(undefined=StrictUndefined, autoescape=False, trim_blocks=False, lstrip_blocks=False)
        try:
            jtpl = env.from_string(template)
            return jtpl.render(**context)
        except Exception:
            # If Jinja2 rendering fails, use fallback to be resilient
            return _render_with_fallback(template, context)

    return _render_with_fallback(template, context)


