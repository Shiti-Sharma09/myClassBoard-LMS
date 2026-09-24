"""Student self-study quiz from one of their notes. Ephemeral: nothing is saved, and it never
reaches the teacher's Question Bank (that is the separate, teacher-reviewed generator)."""

from pydantic import BaseModel, Field, model_validator

from app.ai import AIService

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


def make_quiz(ai: AIService, note_text: str, count: int = 5) -> list[PracticeQuestion]:
    quiz = ai.run_json(
        "practice_quiz",
        {"note_text": note_text[:MAX_NOTE_CHARS], "count": count},
        PracticeQuiz,
        model="fast",
    )
    return quiz.questions[:count]
