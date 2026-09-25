"""Marking a submitted test. Code marks everything it can; the model marks only written answers, and
only into three steps (0, half, full), so it cannot invent odd marks. If the model is unavailable,
written answers are marked by keyword overlap and flagged, never left blank."""

import json
import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Literal

from pydantic import BaseModel, Field

from app.ai import AIError, AIService
from app.services.dedupe import tokens

OBJECTIVE = ("mcq", "true_false", "fill_blank")
WRITTEN = ("short", "long")
MAX_ANSWER_CHARS = 1500  # a Class 6 answer is never this long; also caps what is sent to the model
_PUNCT = re.compile(r"[^a-z0-9 ]+")
_ARTICLE = re.compile(r"^(?:a|an|the) ")


@dataclass
class Marked:
    marks: float
    feedback: str | None
    scored_by: str  # code | ai | keyword


def normalise(text: str) -> str:
    """Lower-case, no punctuation, single spaces, no leading a/an/the: the "little trimming" for fill-ins."""
    cleaned = " ".join(_PUNCT.sub(" ", text.lower()).split())
    return _ARTICLE.sub("", cleaned)


def _alternatives(key: str) -> list[str]:
    return [normalise(part) for part in re.split(r"\s*(?:/|;|\bor\b)\s*", key) if part.strip()]


def is_correct(qtype: str, key: str, given: str) -> bool:
    """Objective marking. Fill-in accepts alternatives written as "a / b" and one small typo in longer words."""
    got = normalise(given)
    if not got:
        return False
    if qtype in ("mcq", "true_false"):
        return got == normalise(key)
    for alt in _alternatives(key):
        if got == alt:
            return True
        if len(alt) >= 5 and SequenceMatcher(None, got, alt).ratio() >= 0.86:
            return True
    return False


def mark_objective(qtype: str, key: str, given: str, max_marks: float) -> Marked:
    ok = is_correct(qtype, key, given)
    return Marked(max_marks if ok else 0.0, None if ok else f"The correct answer is: {key}", "code")


def keyword_fraction(key: str, given: str) -> float:
    """Fallback for written answers: how much of the key's meaningful words appear in the answer."""
    key_words, got_words = tokens(key), tokens(given)
    if not key_words or not got_words:
        return 0.0
    share = len(key_words & got_words) / len(key_words)
    return 1.0 if share >= 0.7 else 0.5 if share >= 0.35 else 0.0


class _Result(BaseModel):
    id: int
    score: Literal[0, 0.5, 1]
    reason: str = Field(default="", max_length=400)


class _Batch(BaseModel):
    results: list[_Result]


@dataclass
class WrittenItem:
    question_id: int
    question: str
    key: str
    answer: str
    max_marks: float


def _round_half(x: float) -> float:
    return round(x * 2) / 2


def mark_written(ai: AIService, items: list[WrittenItem]) -> tuple[dict[int, Marked], bool]:
    """(results by question id, whether the keyword fallback had to be used for any answer)."""
    results: dict[int, Marked] = {}
    todo = []
    for item in items:
        if not item.answer.strip():
            results[item.question_id] = Marked(0.0, "No answer was given.", "code")
        else:
            todo.append(item)
    if not todo:
        return results, False

    payload = [
        {"id": i.question_id, "question": i.question, "model_answer": i.key, "max_marks": i.max_marks, "student_answer": i.answer[:MAX_ANSWER_CHARS]}
        for i in todo
    ]
    by_id: dict[int, _Result] = {}
    try:
        batch = ai.run_json("score_answers", {"items_json": json.dumps(payload, indent=1)}, _Batch, temperature=0)
        by_id = {r.id: r for r in batch.results}
    except AIError:
        by_id = {}

    fallback = False
    for item in todo:
        r = by_id.get(item.question_id)
        if r is not None:
            results[item.question_id] = Marked(_round_half(r.score * item.max_marks), r.reason or None, "ai")
        else:  # the model skipped this one, or was unavailable
            fallback = True
            fraction = keyword_fraction(item.key, item.answer)
            results[item.question_id] = Marked(
                _round_half(fraction * item.max_marks),
                f"Marked automatically by matching key words. Model answer: {item.key}",
                "keyword",
            )
    return results, fallback
