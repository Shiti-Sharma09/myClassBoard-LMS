"""Question generation with checks in code.

The model writes questions; code decides which ones are acceptable:
  * lenient parsing (one odd label must not throw away a whole 3,000-token reply),
  * strict validation per question type,
  * a grounding check (a multiple-choice or fill-in answer must use words that are in the note),
  * de-duplication against the same batch and earlier versions,
  * exactly N returned when the note supports it. We ask for a few extra, keep the best N, and
    top up if still short. If the note cannot support N, we say so instead of inventing filler.
"""

import logging
import math
import random
import re
import time
from dataclasses import dataclass, field

from pydantic import BaseModel, field_validator

from app.ai import AIService
from app.services.chunking import Section, build_context, split_sections
from app.services.dedupe import find_duplicate, tokens

log = logging.getLogger("questions")

QUESTION_TYPES = ("mcq", "short", "long", "fill_blank", "true_false")
TYPE_LABELS = {
    "mcq": "multiple-choice (exactly 4 options)",
    "short": "short answer (a one or two sentence answer)",
    "long": "long answer (a paragraph of reasoning or explanation)",
    "fill_blank": "fill in the blank (one blank written as _____)",
    "true_false": 'true/false (options exactly ["True", "False"])',
}
_ALIASES = {
    "multiple_choice": "mcq", "multiplechoice": "mcq", "mcqs": "mcq", "multiple_choice_question": "mcq",
    "short_answer": "short", "short_answer_question": "short",
    "long_answer": "long", "long_answer_question": "long", "essay": "long",
    "fill_in_the_blank": "fill_blank", "fill_in_the_blanks": "fill_blank", "fill_blanks": "fill_blank", "fill_in_blank": "fill_blank", "fillblank": "fill_blank",
    "true_or_false": "true_false", "truefalse": "true_false", "true/false": "true_false", "tf": "true_false", "boolean": "true_false",
}
DEFAULT_MARKS = {"mcq": 1.0, "true_false": 1.0, "fill_blank": 1.0, "short": 2.0, "long": 5.0}
BLOOM_LEVELS = ("Remember", "Understand", "Apply", "Analyze", "Evaluate", "Create")
DIFFICULTIES = ("easy", "medium", "hard")

# Roughly 2,750 tokens of note text. With the prompt, the schema, earlier questions to avoid and up to
# ~3,000 output tokens this stays under the 8,000 tokens/minute free-tier cap.
CONTEXT_BUDGET_CHARS = 11_000
MAX_OUTPUT_TOKENS = 3_200
MAX_PER_CALL = 15
MAX_TOPUPS = 2
TOPUP_TIME_BUDGET_S = 40  # stop asking for more once this much time has passed
AVOID_LIMIT = 40  # earlier questions shown to the model so it doesn't repeat them (about 25 tokens each)

VERSION_NAMES = {1: "balanced", 2: "application", 3: "recall"}
MAX_VERSIONS = len(VERSION_NAMES)


def emphasis_for(version: int, total: int) -> str:
    """What this version should focus on, with concrete numbers (models follow counts better than adjectives)."""
    if version == 2:
        need = math.ceil(total / 2)
        return (
            f"Application and reasoning. At least {need} of the {total} questions MUST have bloom Apply, Analyze or Evaluate "
            "(real-life situations, cause and effect, comparing, predicting, explaining why). Avoid pure recall."
        )
    if version == 3:
        need = math.ceil(total * 0.7)
        return (
            f"Recall and revision. At least {need} of the {total} questions MUST have bloom Remember or Understand "
            "(key terms, definitions, facts, labelling, true/false misconceptions). Give extra attention to any weak topics listed."
        )
    return "Balanced. A healthy spread across Remember, Understand and Apply, covering many different topics."


# ------------------------------------------------------------------ what the model returns (lenient)


class RawQuestion(BaseModel):
    type: str
    question: str
    options: list[str] | None = None
    answer: str
    explanation: str = ""
    difficulty: str = "medium"
    bloom: str = "Understand"
    topic: str = ""

    @field_validator("answer", "type", "question", "difficulty", "bloom", "topic", "explanation", mode="before")
    @classmethod
    def _to_text(cls, value):
        return "" if value is None else str(value)


class RawBatch(BaseModel):
    questions: list[RawQuestion]
    insufficient: bool = False  # the model says the notes cannot support this many questions


# ------------------------------------------------------------------ what we keep


@dataclass
class ValidQuestion:
    type: str
    text: str
    options: list[str] | None
    answer: str
    explanation: str
    difficulty: str
    bloom: str
    topic: str

    @property
    def marks(self) -> float:
        return DEFAULT_MARKS[self.type]


@dataclass
class GenerationResult:
    questions: list[ValidQuestion]
    shortfall: str | None = None
    ai_calls: int = 0
    rejected: dict[str, int] = field(default_factory=dict)
    duplicate_pairs: list[tuple[str, str]] = field(default_factory=list)  # (rejected, matched), for debugging
    rejected_examples: list[tuple[str, str, str]] = field(default_factory=list)  # (reason, question, answer)


_BLANK = re.compile(r"_{2,}|…{2,}|\.{4,}")
_OPTION_PREFIX = re.compile(r"^\(?[A-Da-d][).:]\s+")
_LETTER = re.compile(r"^\(?([A-Da-d])[).:]?$")


def normalise_type(raw: str) -> str:
    key = re.sub(r"[\s\-]+", "_", raw.strip().lower())
    return _ALIASES.get(key, key)


def _clean_options(options: list[str] | None) -> list[str]:
    options = [str(o).strip() for o in (options or []) if str(o).strip()]
    if options and all(_OPTION_PREFIX.match(o) for o in options):
        options = [_OPTION_PREFIX.sub("", o).strip() for o in options]
    return options


def _grounded(answer: str, note_tokens: frozenset[str]) -> bool:
    """Every reasonably long word of the answer must appear somewhere in the note."""
    return all(t in note_tokens for t in tokens(answer) if len(t) >= 4 and not t.isdigit())


def validate_question(raw: RawQuestion, allowed: set[str], note_tokens: frozenset[str]) -> ValidQuestion | str:
    """Returns a ValidQuestion, or a short reason string if the question is rejected."""
    qtype = normalise_type(raw.type)
    if qtype not in QUESTION_TYPES:
        return "unknown type"
    if qtype not in allowed:
        return "type not requested"
    text, answer = raw.question.strip(), raw.answer.strip()
    if len(text) < 8 or not answer:
        return "empty question or answer"

    options: list[str] | None = None
    if qtype == "mcq":
        options = _clean_options(raw.options)
        if len(options) != 4 or len({o.casefold() for o in options}) != 4:
            return "mcq needs 4 distinct options"
        letter = _LETTER.match(answer)
        by_text = [o for o in options if o.casefold() == _OPTION_PREFIX.sub("", answer).strip().casefold()]
        if by_text:
            answer = by_text[0]
        elif letter:
            answer = options["ABCD".index(letter.group(1).upper())]
        else:
            return "mcq answer is not one of the options"
        random.Random(text).shuffle(options)  # models favour B and C: spread the correct answer around
    elif qtype == "true_false":
        low = answer.strip().rstrip(".").casefold()
        if low not in ("true", "false"):
            return "true/false answer must be True or False"
        answer, options = low.capitalize(), ["True", "False"]
    elif qtype == "fill_blank":
        if not _BLANK.search(text):
            return "fill-in question has no blank"
        text = _BLANK.sub("_____", text, count=1)
        if len(answer.split()) > 6:
            return "fill-in answer too long"
    elif qtype == "short" and len(answer.split()) < 2:
        return "short answer too thin"
    elif qtype == "long" and len(answer.split()) < 6:
        return "long answer too thin"

    if qtype in ("mcq", "fill_blank") and not _grounded(answer, note_tokens):
        return "answer not found in the note"

    difficulty = raw.difficulty.strip().lower()
    bloom = raw.bloom.strip().capitalize()
    return ValidQuestion(
        type=qtype,
        text=text,
        options=options,
        answer=answer,
        explanation=raw.explanation.strip() or "See the note.",
        difficulty=difficulty if difficulty in DIFFICULTIES else "medium",
        bloom=bloom if bloom in BLOOM_LEVELS else "Understand",
        topic=raw.topic.strip()[:200] or "General",
    )


# ------------------------------------------------------------------ counts and selection


def split_counts(n: int, types: list[str]) -> dict[str, int]:
    """Spread n questions over the chosen types as evenly as possible (earlier types get the extra)."""
    base, extra = divmod(n, len(types))
    return {t: base + (1 if i < extra else 0) for i, t in enumerate(types)}


def select_questions(pool: list[ValidQuestion], targets: dict[str, int], n: int) -> list[ValidQuestion]:
    """Keep up to n questions, meeting each type's target first, then filling with whatever is left."""
    chosen: list[ValidQuestion] = []
    used: set[int] = set()
    for qtype, want in targets.items():
        for i, q in enumerate(pool):
            if want <= 0:
                break
            if q.type == qtype and i not in used:
                chosen.append(q)
                used.add(i)
                want -= 1
    for i, q in enumerate(pool):
        if len(chosen) >= n:
            break
        if i not in used:
            chosen.append(q)
            used.add(i)
    return chosen[:n]


def _ask_counts(deficits: dict[str, int], extra: int) -> dict[str, int]:
    """How many of each type to request: the deficit plus a few spares, spread over the wanted types."""
    ask = dict(deficits)
    wanted = [t for t, d in deficits.items() if d > 0]
    for i in range(extra if wanted else 0):
        ask[wanted[i % len(wanted)]] += 1
    return {t: c for t, c in ask.items() if c > 0}


def _difficulty_rule(difficulty: str) -> str:
    if difficulty == "mixed":
        return "a mix: about 40% easy, 40% medium and 20% hard"
    return f"all {difficulty}"


# ------------------------------------------------------------------ orchestration

_RECAP = re.compile(r"(key terms?|quick recap|recap|summary|glossary|revision|key points)", re.IGNORECASE)


def is_recap(title: str) -> bool:
    return bool(_RECAP.search(title))


def _without_recaps(sections: list[Section]) -> list[Section]:
    """Recap and glossary sections restate facts from the main text, so questions from them would only
    repeat questions from the main sections. Skipped unless they are all there is."""
    main = [s for s in sections if not is_recap(s.title)]
    return main or sections


def generate(
    ai: AIService,
    *,
    note_title: str,
    note_text: str,
    subject: str,
    grade: int,
    chapter_title: str | None,
    count: int,
    types: list[str],
    difficulty: str,
    version: int,
    prior: list[tuple[str, str]],
    section_indices: list[int] | None = None,
    weak_topics: list[str] | None = None,
) -> GenerationResult:
    """Produce up to `count` valid, distinct, grounded questions for one version of a note."""
    sections = split_sections(note_text, note_title)
    if section_indices:
        wanted = set(section_indices)
        sections = [s for s in sections if s.index in wanted] or sections
    # If the teacher picked sections explicitly, honour that exactly. Otherwise skip recap sections.
    chosen = sections if section_indices else _without_recaps(sections)
    context = build_context(chosen, CONTEXT_BUDGET_CHARS, version)
    note_tokens = tokens(note_text)
    targets = split_counts(count, types)

    pool: list[ValidQuestion] = []
    seen: list[tuple[str, str]] = list(prior)
    rejected: dict[str, int] = {}
    pairs: list[tuple[str, str]] = []
    examples: list[tuple[str, str, str]] = []
    calls = 0
    insufficient = False

    started = time.monotonic()
    for attempt in range(1 + MAX_TOPUPS):
        have = select_questions(pool, targets, count)
        if len(have) >= count:
            break
        if attempt > 0 and time.monotonic() - started > TOPUP_TIME_BUDGET_S:
            break  # each extra call can wait out the rate limit; better to return what we have than make the teacher wait
        deficits = {t: max(0, targets[t] - sum(1 for q in have if q.type == t)) for t in targets}
        spare = 0.5 if prior else 0.2  # later versions lose more questions to duplicates, so ask for more spares
        extra = max(2, math.ceil(spare * (count - len(have)))) if attempt == 0 else 1
        ask = _ask_counts(deficits, extra)
        total_ask = min(sum(ask.values()), MAX_PER_CALL)
        avoid = [t[:100] for t, _ in seen[-AVOID_LIMIT:]]

        batch = ai.run_json(
            "question_gen",
            {
                "subject": subject,
                "grade": grade,
                "chapter": chapter_title,
                "sections": [{"title": s.title, "text": s.text} for s in context],
                "type_targets": [(TYPE_LABELS[t], c) for t, c in ask.items()],
                "total": total_ask,
                "difficulty_rule": _difficulty_rule(difficulty),
                "emphasis": emphasis_for(version, total_ask),
                "weak_topics": weak_topics or [],
                "avoid": avoid,
            },
            RawBatch,
            model="main",
            temperature=0.6,
            max_tokens=MAX_OUTPUT_TOKENS,
        )
        calls += 1
        fresh = 0
        for raw in batch.questions:
            result = validate_question(raw, set(types), note_tokens)
            if isinstance(result, str):
                rejected[result] = rejected.get(result, 0) + 1
                examples.append((result, raw.question, raw.answer))
                continue
            twin = find_duplicate(result.text, result.answer, seen)
            if twin:
                rejected["duplicate"] = rejected.get("duplicate", 0) + 1
                pairs.append((result.text, twin))
                continue
            pool.append(result)
            seen.append((result.text, result.answer))
            fresh += 1
        log.info("question_gen version=%s attempt=%s asked=%s valid_new=%s rejected=%s", version, attempt + 1, total_ask, fresh, rejected)
        if batch.insufficient or fresh == 0:
            insufficient = insufficient or batch.insufficient
            break  # more calls would just repeat themselves: report honestly instead

    final = select_questions(pool, targets, count)
    shortfall = None
    if len(final) < count:
        got = len(final)
        plural = "s" if got != 1 else ""
        if not got:
            shortfall = "No good questions could be made from this note. It may be too short or too general."
        elif prior:
            shortfall = (
                f"Only {got} new question{plural} that differ from your earlier versions could be made from this note "
                f"(you asked for {count}). Add more content, or choose fewer questions."
            )
        else:
            shortfall = (
                f"This note only supported {got} good question{plural} (you asked for {count}). "
                "Add more content to the note, choose fewer questions, or pick different topics."
            )
    return GenerationResult(final, shortfall, calls, rejected, pairs, examples)
