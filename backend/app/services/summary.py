"""Parent Summary: the AI narrates numbers that code already computed, and code checks the result.

Flow: facts (metrics.py) -> model writes a Narrative -> verify (every number must exist in the facts,
no ranking language) -> one retry with the problems listed -> if still wrong, a plain template
written by code. So a summary with a wrong number can never reach a teacher's screen.
"""

import json
import re
from dataclasses import dataclass

from pydantic import BaseModel, Field

from app.ai import AIError, AIService

MAX_LIST = 3
_NUMBER = re.compile(r"\d+(?:\.\d+)?")
# Parents must not be shown comparisons with other children or alarming labels (agreed rule: no rank bands).
_FORBIDDEN = re.compile(r"\b(rank\w*|topper\w*|classmates?|other (?:students|children|kids)|percentile|fail\w*|behind)\b", re.I)


class Narrative(BaseModel):
    overall: str = Field(min_length=20, max_length=700)
    strengths: list[str] = Field(min_length=1, max_length=MAX_LIST)
    areas_to_work_on: list[str] = Field(default_factory=list, max_length=MAX_LIST)
    trend: str = Field(min_length=5, max_length=400)
    home_tips: list[str] = Field(min_length=2, max_length=MAX_LIST)


def _texts(n: Narrative) -> list[str]:
    return [n.overall, n.trend, *n.strengths, *n.areas_to_work_on, *n.home_tips]


def _numbers(text: str) -> set[float]:
    return {float(m) for m in _NUMBER.findall(text)}


def allowed_numbers(facts: dict) -> set[float]:
    """Every number that appears anywhere in the facts, including inside names ("Unit Test 3")."""
    return _numbers(json.dumps(facts, default=str))


def problems(narrative: Narrative, facts: dict) -> list[str]:
    """Reasons this narrative must not be shown. Empty means it is fine."""
    found: list[str] = []
    allowed = allowed_numbers(facts)
    bad = sorted({m for t in _texts(narrative) for m in _numbers(t) if m not in allowed})
    if bad:
        found.append("These numbers are not in the facts: " + ", ".join(f"{b:g}" for b in bad) + ". Use only numbers from the facts, and do not describe ranges such as 'the 80s'.")
    words = sorted({m.group(0).lower() for t in _texts(narrative) for m in _FORBIDDEN.finditer(t)})
    if words:
        found.append("Do not use these words: " + ", ".join(words) + ". Never compare with other children or use alarming labels.")
    return found


def narration_facts(facts: dict, student_name: str) -> dict:
    """The compact version the model sees (the per-topic list stays out of the prompt to save tokens)."""
    return {
        "student": student_name,
        "tests_taken": facts["tests_count"],
        "overall_percent": facts["overall_percent"],
        "weak_below_percent": facts["weak_threshold"],
        "trend": facts["trend"],
        "trend_from_percent": facts["trend_from"],
        "trend_to_percent": facts["trend_to"],
        "tests": facts["tests"],
        "chapters": facts["chapters"],
        "strongest_topics": facts["strongest"],
        "topics_needing_work": facts["weak_topics"][:MAX_LIST],
    }


def template_narrative(facts: dict, student_name: str) -> Narrative:
    """A plain, always-correct summary written by code. Used only if the model cannot produce a verified one."""
    first = student_name.split()[0]
    overall = facts["overall_percent"]
    strong = facts["strongest"]
    weak = facts["weak_topics"][:MAX_LIST]
    trend_text = {
        "improving": f"{first}'s recent test results ({facts['trend_to']}%) are higher than the earlier ones ({facts['trend_from']}%). That is good progress.",
        "declining": f"{first}'s recent test results ({facts['trend_to']}%) are a little lower than the earlier ones ({facts['trend_from']}%). A bit of steady revision should help.",
        "steady": f"{first}'s results have stayed steady across the tests, at around {facts['trend_to']}%.",
        "not_enough_data": f"There are not enough tests yet to describe a trend for {first}.",
    }[facts["trend"]]
    return Narrative(
        overall=f"{first} has an overall score of {overall}% across {facts['tests_count']} science tests this term.",
        strengths=[f"{s['topic']} ({s['percent']}%)" for s in strong] or [f"{first} has completed all {facts['tests_count']} tests."],
        areas_to_work_on=[f"{w['topic']} ({w['percent']}%)" for w in weak],
        trend=trend_text,
        home_tips=[
            "Spend a short time each day going over the school notes together.",
            "Ask your child to explain one topic to you in their own words.",
        ],
    )


@dataclass
class SummaryResult:
    narrative: Narrative
    source: str  # "ai" or "template"
    verify_failures: int  # how many model attempts were rejected by the checks
    ai_error: str | None = None
    rejected_reasons: list[str] | None = None  # what the checks objected to, kept for the eval report


def narrate(ai: AIService, facts: dict, student_name: str) -> SummaryResult:
    """Model narrative with up to one corrected retry; template if that still fails or the AI is unavailable."""
    variables = {"facts_json": json.dumps(narration_facts(facts, student_name), indent=1), "feedback": ""}
    failures = 0
    reasons: list[str] = []
    for _ in range(2):
        try:
            narrative = ai.run_json("parent_summary", variables, Narrative, temperature=0.3)
        except AIError as exc:
            return SummaryResult(template_narrative(facts, student_name), "template", failures, str(exc), reasons)
        issues = problems(narrative, facts)
        if not issues:
            return SummaryResult(narrative, "ai", failures, rejected_reasons=reasons)
        failures += 1
        reasons += issues
        variables["feedback"] = " ".join(issues)
    return SummaryResult(template_narrative(facts, student_name), "template", failures, rejected_reasons=reasons)
