"""Split a note into sections ("topics") and build a size-bounded slice of it for the AI.

Why this exists: the free tier allows 8,000 tokens per minute, and a 10-page note alone is
about 5,500 tokens. So we never send a whole document. We split it into sections in code (no AI
call), then send a bounded slice. Each *version* reads a different share of the note, so versions
2 and 3 see different content, which also keeps their questions from repeating.
"""

import re
from dataclasses import dataclass

# "1. Introduction", "## Magnets", "Chapter 3: Water": short, no sentence punctuation at the end
_HEADING = re.compile(r"^(?:#{1,3}\s+|\d{1,2}[.)]\s+)(?P<title>[^\n]{3,90})$")
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")

MIN_SECTION_CHARS = 250  # smaller sections are folded into the previous one
MAX_SECTION_CHARS = 5000  # bigger ones are split at paragraph breaks
WINDOW_CHARS = 600  # size of the pieces the note is cut into when it is too big to send whole
DEAL_WAYS = 3  # one share per version (there are up to 3 versions)


@dataclass
class Section:
    index: int
    title: str
    text: str

    @property
    def words(self) -> int:
        return len(self.text.split())


def _as_heading(line: str) -> str | None:
    line = line.strip()
    match = _HEADING.match(line)
    if not match:
        return None
    title = match.group("title").strip()
    if title.endswith((".", ",", ";", "?", "!")) or len(title.split()) > 9:
        return None  # a sentence or list item, not a heading
    return title.rstrip(":")


def split_sections(text: str, fallback_title: str = "Introduction") -> list[Section]:
    """Sections by heading. With no headings, chunks by paragraph. Never returns empty text."""
    raw: list[tuple[str, list[str]]] = []
    current: tuple[str, list[str]] = (fallback_title, [])
    saw_heading = False
    for line in text.splitlines():
        title = _as_heading(line)
        if title:
            saw_heading = True
            if "".join(current[1]).strip():
                raw.append(current)
            current = (title, [])
        else:
            current[1].append(line)
    if "".join(current[1]).strip():
        raw.append(current)

    if not saw_heading:
        raw = [(f"Part {i}", [chunk]) for i, chunk in enumerate(_by_paragraph("\n".join(raw[0][1]) if raw else text, 2500), 1)]

    # fold tiny sections into the previous one, split huge ones
    merged: list[tuple[str, str]] = []
    for title, lines in raw:
        body = "\n".join(lines).strip()
        if merged and len(body) < MIN_SECTION_CHARS:
            merged[-1] = (merged[-1][0], merged[-1][1] + "\n" + (title + ". " if title else "") + body)
        else:
            merged.append((title, body))
    if len(merged) > 1 and len(merged[0][1]) < MIN_SECTION_CHARS:
        # a tiny opening (just a title or subtitle) belongs with the first real section, not on its own
        merged[1] = (merged[1][0], merged[0][1] + "\n" + merged[1][1])
        merged.pop(0)
    sections: list[Section] = []
    for title, body in merged:
        parts = _by_paragraph(body, MAX_SECTION_CHARS) if len(body) > MAX_SECTION_CHARS else [body]
        for n, part in enumerate(parts, 1):
            sections.append(Section(len(sections), title if n == 1 else f"{title} (part {n})", part))
    return sections


def _by_paragraph(text: str, limit: int) -> list[str]:
    chunks, current = [], ""
    for para in re.split(r"\n\s*\n|\n(?=[-•*] )", text):
        para = para.strip()
        if not para:
            continue
        if current and len(current) + len(para) + 1 > limit:
            chunks.append(current)
            current = ""
        current = f"{current}\n{para}".strip()
    if current:
        chunks.append(current)
    return chunks or [text.strip()]


def _windows(text: str, cap: int) -> list[str]:
    """Cut text into pieces of about `cap` characters, ending at sentence boundaries."""
    windows, current = [], ""
    for sentence in _SENTENCE_END.split(text.strip()):
        if current and len(current) + len(sentence) + 1 > cap:
            windows.append(current)
            current = ""
        current = f"{current} {sentence}".strip()
    if current:
        windows.append(current)
    return windows or [text.strip()]


def build_context(sections: list[Section], budget_chars: int, version: int = 1) -> list[Section]:
    """The part of the note this version should read, at most `budget_chars` long.

    If the whole note fits, every version gets all of it. Otherwise the note is cut into windows and
    dealt out like cards: version 1 gets windows 0, 3, 6..., version 2 gets 1, 4, 7..., version 3 gets
    2, 5, 8... So each version reads different content, which is what keeps regenerated versions from
    repeating each other. Windows keep their section title so topics stay meaningful.
    """
    if not sections:
        return []
    if sum(len(s.text) for s in sections) <= budget_chars:
        return list(sections)

    pieces = [(s, w) for s in sections for w in _windows(s.text, WINDOW_CHARS)]
    mine = [p for i, p in enumerate(pieces) if i % DEAL_WAYS == (version - 1) % DEAL_WAYS]
    while sum(len(w) for _, w in mine) > budget_chars and len(mine) > 1:
        step = len(mine) / (len(mine) - 1)  # drop one piece, evenly spread, until it fits
        mine = [mine[int(i * step)] for i in range(len(mine) - 1)]

    out: list[Section] = []
    for section, window in mine:
        if out and out[-1].index == section.index:
            out[-1] = Section(section.index, section.title, f"{out[-1].text} {window}")
        else:
            out.append(Section(section.index, section.title, window))
    return out
