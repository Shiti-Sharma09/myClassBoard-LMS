"""Checks a teacher's edit to a question, so an edited question is still a valid one."""

import re

from app.models import Question
from app.services.question_gen import BLOOM_LEVELS, DIFFICULTIES

_BLANK = re.compile(r"_{2,}")
STATUSES = ("draft", "accepted", "discarded")
CONTENT_FIELDS = ("text", "options", "answer", "explanation", "difficulty", "bloom", "topic")


class EditError(ValueError):
    """The edit would leave the question invalid. The message is safe to show the teacher."""


def apply_edit(question: Question, changes: dict) -> None:
    """Apply `changes` (already limited to fields the teacher sent) to `question`, or raise EditError."""
    text = changes.get("text", question.text)
    options = changes.get("options", question.options)
    answer = changes.get("answer", question.answer)

    if "text" in changes and len(text.strip()) < 8:
        raise EditError("The question is too short.")
    if "answer" in changes and not answer.strip():
        raise EditError("Every question needs an answer.")

    if question.type == "mcq":
        options = [o.strip() for o in (options or []) if o.strip()]
        if len(options) != 4 or len({o.casefold() for o in options}) != 4:
            raise EditError("A multiple-choice question needs 4 different options.")
        if answer.strip().casefold() not in {o.casefold() for o in options}:
            raise EditError("The answer must match one of the options.")
        answer = next(o for o in options if o.casefold() == answer.strip().casefold())
    elif question.type == "true_false":
        if answer.strip().capitalize() not in ("True", "False"):
            raise EditError("The answer must be True or False.")
        answer, options = answer.strip().capitalize(), ["True", "False"]
    elif question.type == "fill_blank" and not _BLANK.search(text):
        raise EditError("A fill-in-the-blank question needs a blank (_____).")

    if "difficulty" in changes and changes["difficulty"] not in DIFFICULTIES:
        raise EditError("Difficulty must be easy, medium or hard.")
    if "bloom" in changes and changes["bloom"] not in BLOOM_LEVELS:
        raise EditError("That isn't a Bloom's taxonomy level.")
    if "marks" in changes and not 0 <= changes["marks"] <= 100:
        raise EditError("Marks must be between 0 and 100.")
    if "status" in changes and changes["status"] not in STATUSES:
        raise EditError("Status must be draft, accepted or discarded.")
    if "topic" in changes and not changes["topic"].strip():
        raise EditError("Give the question a topic.")

    changed_content = False
    for key, value in changes.items():
        if key == "options":
            value = options
        elif key == "answer":
            value = answer
        elif isinstance(value, str):
            value = value.strip()
        if getattr(question, key) != value:
            setattr(question, key, value)
            changed_content = changed_content or key in CONTENT_FIELDS
    if question.type in ("mcq", "true_false") and (question.options != options or question.answer != answer):
        question.options, question.answer = options, answer
    if changed_content:
        question.edited = True
