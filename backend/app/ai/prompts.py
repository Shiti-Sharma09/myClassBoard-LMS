"""Versioned prompt templates.

Prompts live in app/prompts as `<name>.v<N>.md` files, never as inline strings.
A file may hold a system part and a user part separated by a line containing only
`=== USER ===`. Without that marker the whole file is the user message.
Templates use Jinja2 and fail loudly if a variable is missing.
"""

import re
from dataclasses import dataclass
from pathlib import Path

from jinja2 import Environment, StrictUndefined

PROMPT_DIR = Path(__file__).resolve().parent.parent / "prompts"
_SPLIT = re.compile(r"^=== USER ===\s*$", re.MULTILINE)
_env = Environment(undefined=StrictUndefined, keep_trailing_newline=False, autoescape=False)


@dataclass
class RenderedPrompt:
    name: str
    version: int
    system: str | None
    user: str


def _latest_version(name: str) -> int:
    versions = [
        int(m.group(1))
        for p in PROMPT_DIR.glob(f"{name}.v*.md")
        if (m := re.fullmatch(rf"{re.escape(name)}\.v(\d+)\.md", p.name))
    ]
    if not versions:
        raise FileNotFoundError(f"No prompt template named '{name}' in {PROMPT_DIR}")
    return max(versions)


def render_prompt(name: str, variables: dict | None = None, version: int | None = None) -> RenderedPrompt:
    version = version or _latest_version(name)
    path = PROMPT_DIR / f"{name}.v{version}.md"
    if not path.exists():
        raise FileNotFoundError(f"Prompt template not found: {path.name}")
    source = path.read_text(encoding="utf-8")
    parts = _SPLIT.split(source, maxsplit=1)
    system, user = (parts[0], parts[1]) if len(parts) == 2 else (None, parts[0])
    variables = variables or {}
    render = lambda text: _env.from_string(text).render(**variables).strip()  # noqa: E731
    return RenderedPrompt(name, version, render(system) if system else None, render(user))
