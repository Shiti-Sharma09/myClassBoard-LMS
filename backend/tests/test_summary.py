import json
from datetime import date

import pytest

from app.ai import AIError, AIService
from app.config import Settings
from app.services.metrics import Record, compute_facts
from app.services.summary import Narrative, narrate, problems, template_narrative
from tests.conftest import ScriptedProvider

RECORDS = [
    Record("Poles", "Exploring Magnets", "Unit Test 3", date(2026, 8, 17), 4, 10),
    Record("Uses", "Exploring Magnets", "Unit Test 3", date(2026, 8, 17), 9, 10),
    Record("Units", "Measurement", "Unit Test 4", date(2026, 8, 31), 8, 10),
    Record("Motion", "Measurement", "Unit Test 4", date(2026, 8, 31), 7, 10),
]
FACTS = compute_facts(RECORDS, 60)  # overall 70, Poles 40 (weak), Uses 90, Units 80, Motion 70


def narrative(**kw) -> Narrative:
    base = dict(
        overall="Aarav scored 70% overall across 2 tests, which is a solid result.",
        strengths=["Uses of Magnets did very well at 90%."],
        areas_to_work_on=["Poles of a magnet at 40% needs some practice."],
        trend="Results are steady across the tests.",
        home_tips=["Look at bar magnets together at home.", "Ask your child to explain how poles behave."],
    )
    return Narrative(**{**base, **kw})


def test_a_narrative_that_only_restates_the_facts_passes():
    assert problems(narrative(), FACTS) == []


def test_an_invented_number_is_caught_anywhere_in_the_text():
    assert "85" in problems(narrative(overall="Aarav scored 85% overall across 2 tests."), FACTS)[0]
    assert problems(narrative(home_tips=["Practise for 20 minutes a day.", "Ask questions."]), FACTS)
    assert problems(narrative(strengths=["Scored 9.5 marks."]), FACTS)


def test_numbers_inside_names_and_dates_are_allowed():
    assert problems(narrative(trend="After Unit Test 3 and Unit Test 4 results are steady."), FACTS) == []


def test_ranking_and_alarming_language_is_caught():
    for bad in ["Aarav is the class topper.", "Ranked first among classmates.", "Aarav is failing Poles.", "Better than other students."]:
        issues = problems(narrative(overall=bad + " Overall 70%."), FACTS)
        assert any("Do not use" in i for i in issues), bad


def test_the_template_is_always_correct_and_passes_the_same_checks():
    t = template_narrative(FACTS, "Aarav Sharma")
    assert problems(t, FACTS) == []
    assert "70%" in t.overall and "Poles (40%)" in t.areas_to_work_on[0]


def test_template_handles_no_weak_topics_and_no_trend():
    facts = compute_facts([Record("A", "C", "T1", date(2026, 8, 1), 9, 10)], 60)
    t = template_narrative(facts, "Diya Nair")
    assert t.areas_to_work_on == [] and "not enough tests" in t.trend and problems(t, facts) == []


# ---- orchestration with a scripted model


@pytest.fixture
def ai():
    provider = ScriptedProvider()
    return AIService(provider, Settings(groq_api_key="test"), sleep=lambda _: None), provider


def reply(n: Narrative) -> str:
    return n.model_dump_json()


def test_a_good_first_reply_is_used_as_is(ai):
    service, provider = ai
    provider.replies.append(reply(narrative()))
    result = narrate(service, FACTS, "Aarav Sharma")
    assert (result.source, result.verify_failures) == ("ai", 0) and len(provider.calls) == 1
    facts_in_prompt = provider.calls[0]["messages"][1]["content"]
    assert '"overall_percent": 70' in facts_in_prompt and "Poles" in facts_in_prompt


def test_a_bad_number_triggers_one_corrected_retry(ai):
    service, provider = ai
    provider.replies += [reply(narrative(overall="Aarav scored 85% overall across 2 tests, well done.")), reply(narrative())]
    result = narrate(service, FACTS, "Aarav Sharma")
    assert (result.source, result.verify_failures) == ("ai", 1)
    assert "85" in provider.calls[1]["messages"][1]["content"]  # the retry says what was wrong


def test_two_bad_replies_fall_back_to_the_template(ai):
    service, provider = ai
    bad = reply(narrative(overall="Aarav scored 85% overall across 2 tests, well done."))
    provider.replies += [bad, bad]
    result = narrate(service, FACTS, "Aarav Sharma")
    assert (result.source, result.verify_failures) == ("template", 2)
    assert problems(result.narrative, FACTS) == []


def test_an_unavailable_model_still_gives_the_teacher_a_draft(ai):
    service, provider = ai
    provider.replies.append(AIError("The AI is busy."))
    result = narrate(service, FACTS, "Aarav Sharma")
    assert result.source == "template" and result.ai_error == "The AI is busy."


def test_facts_json_is_what_the_model_is_told_to_restate(ai):
    service, provider = ai
    provider.replies.append(reply(narrative()))
    narrate(service, FACTS, "Aarav Sharma")
    prompt = provider.calls[0]["messages"][1]["content"]
    assert json.loads(prompt[prompt.index("{") : prompt.rindex("}") + 1])["overall_percent"] == FACTS["overall_percent"]
