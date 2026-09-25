"""Student self-study quiz from one of their notes. Ephemeral: nothing is saved, and it never
reaches the teacher's Question Bank (that is the separate, teacher-reviewed generator)."""

from pydantic import BaseModel, Field, model_validator

from app.ai import AIService
from app.services.chunking import split_sections
from app.services.dedupe import tokens

MAX_NOTE_CHARS = 8000  # about 2,000 tokens: keeps a call well inside the 8k tokens/minute free tier
MIN_NOTE_CHARS = 200


class PracticeQuestion(BaseModel):
    question: str = Field(min_length=5)
    options: list[str]
    correct_index: int
    explanation: str

    @model_validator(mode="after")
    def check_options(self):
        if len(self.options) not in (2, 4):
            raise ValueError("options must have 2 (true/false) or 4 (multiple choice) entries")
        if not 0 <= self.correct_index < len(self.options):
            raise ValueError("correct_index must point at one of the options")
        return self


class PracticeQuiz(BaseModel):
    questions: list[PracticeQuestion] = Field(min_length=1)


def focus_text(note_text: str, topic: str) -> str:
    """The parts of a note that talk about `topic`, best match first, within the size budget.

    Falls back to the start of the note when nothing matches, so a quiz can still be made.
    """
    wanted = tokens(topic)
    scored = []
    for section in split_sections(note_text):
        hits = len(wanted & tokens(section.title)) * 3 + len(wanted & tokens(section.text))
        if hits:
            scored.append((hits, section.index, section.text))
    if not scored:
        return note_text[:MAX_NOTE_CHARS]
    best = max(hits for hits, _, _ in scored)
    scored = [entry for entry in scored if entry[0] * 2 >= best]  # drop sections that only mention a word in passing
    picked, used = [], 0
    for _, index, text in sorted(scored, reverse=True):
        if used and used + len(text) > MAX_NOTE_CHARS:
            continue
        picked.append((index, text[:MAX_NOTE_CHARS]))
        used += len(text)
    return "\n\n".join(text for _, text in sorted(picked))[:MAX_NOTE_CHARS]


def make_quiz(ai: AIService, note_text: str, count: int = 5, topic: str | None = None) -> list[PracticeQuestion]:
    text = focus_text(note_text, topic) if topic else note_text
    quiz = ai.run_json(
        "practice_quiz",
        {"note_text": text[:MAX_NOTE_CHARS], "count": count, "topic": topic},
        PracticeQuiz,
        model="fast",
    )
    return quiz.questions[:count]
