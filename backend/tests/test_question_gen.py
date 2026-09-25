import json

import pytest

import app.services.question_gen as qg
from app.ai import AIService
from app.config import Settings
from app.services.dedupe import tokens
from app.services.question_gen import RawQuestion, generate, select_questions, split_counts, validate_question
from tests.conftest import ScriptedProvider
from tests.qhelpers import NOTE_TEXT, POOL, pool, reply

NOTE_TOKENS = tokens(NOTE_TEXT)
ALL_TYPES = list(qg.QUESTION_TYPES)


def raw(**kw) -> RawQuestion:
    base = dict(type="mcq", question="Which material does a magnet attract?", options=["Iron", "Wood", "Glass", "Rubber"], answer="Iron",
                explanation="x", difficulty="easy", bloom="Remember", topic="T")
    return RawQuestion(**{**base, **kw})


def check(r: RawQuestion, allowed=None):
    return validate_question(r, set(allowed or ALL_TYPES), NOTE_TOKENS)


# ---------------------------------------------------------------- validation


def test_valid_mcq_keeps_the_answer_and_shuffles_options():
    q = check(raw())
    assert q.answer == "Iron" and sorted(q.options) == ["Glass", "Iron", "Rubber", "Wood"]


def test_option_order_is_stable_for_the_same_question():
    assert check(raw()).options == check(raw()).options


def test_mcq_answer_given_as_letter_or_with_prefix_is_resolved():
    assert check(raw(answer="B", options=["Wood", "Iron", "Glass", "Rubber"])).answer == "Iron"
    assert check(raw(answer="(b) Iron", options=["Wood", "Iron", "Glass", "Rubber"])).answer == "Iron"
    prefixed = check(raw(options=["A) Wood", "B) Iron", "C) Glass", "D) Rubber"]))
    assert sorted(prefixed.options) == ["Glass", "Iron", "Rubber", "Wood"]


@pytest.mark.parametrize(
    "kw, reason",
    [
        (dict(options=["Iron", "Wood", "Glass"]), "4 distinct"),
        (dict(options=["Iron", "iron", "Glass", "Rubber"]), "4 distinct"),
        (dict(answer="Aluminium"), "not one of the options"),
        (dict(question="Short?"), "empty question"),
        (dict(answer=""), "empty question"),
        (dict(type="riddle"), "unknown type"),
    ],
)
def test_invalid_questions_are_rejected_with_a_reason(kw, reason):
    result = check(raw(**kw))
    assert isinstance(result, str) and reason in result


def test_question_type_names_are_normalised():
    assert check(raw(type="Multiple Choice")).type == "mcq"
    assert check(raw(type="short-answer", options=None, answer="Iron and nickel are magnetic.")).type == "short"
    assert check(raw(type="True/False", question="Every magnet has two poles.", options=None, answer="true.")).answer == "True"
    assert check(raw(type="Fill in the blanks", question="Like poles ____ each other.", options=None, answer="repel")).type == "fill_blank"


def test_type_not_requested_is_rejected():
    assert "not requested" in check(raw(), allowed=["short"])


def test_true_false_needs_a_true_or_false_answer():
    assert "True or False" in check(raw(type="true_false", question="Magnets are useful.", options=None, answer="maybe"))
    q = check(raw(type="true_false", question="Magnets are useful.", options=None, answer="False"))
    assert (q.answer, q.options) == ("False", ["True", "False"])


def test_fill_blank_needs_a_blank_and_a_short_answer():
    assert "no blank" in check(raw(type="fill_blank", question="Like poles repel each other.", options=None, answer="repel"))
    q = check(raw(type="fill_blank", question="Like poles ______ each other.", options=None, answer="repel"))
    assert "_____" in q.text and "______" not in q.text
    assert "too long" in check(raw(type="fill_blank", question="Like poles _____ each other.", options=None, answer="a b c d e f g"))


def test_short_and_long_answers_must_have_substance():
    assert "thin" in check(raw(type="short", options=None, answer="Iron"))
    assert "thin" in check(raw(type="long", options=None, answer="Because poles."))


def test_answers_must_be_grounded_in_the_note():
    outside = check(raw(options=["Iron", "Plutonium", "Glass", "Rubber"], answer="Plutonium"))
    assert "not found in the note" in outside
    fill = check(raw(type="fill_blank", question="The scientist who found this was _____ .", options=None, answer="Oersted"))
    assert "not found in the note" in fill


def test_unknown_difficulty_and_bloom_fall_back_safely():
    q = check(raw(difficulty="HARD-ish", bloom="apply"))
    assert (q.difficulty, q.bloom) == ("medium", "Apply")


def test_missing_fields_from_the_model_are_tolerated():
    r = RawQuestion.model_validate({"type": "mcq", "question": "Which material does a magnet attract?", "options": ["Iron", "Wood", "Glass", "Rubber"], "answer": "Iron"})
    assert check(r).topic == "General"


# ---------------------------------------------------------------- counts


def test_split_counts_spreads_evenly():
    assert split_counts(10, ALL_TYPES) == {"mcq": 2, "short": 2, "long": 2, "fill_blank": 2, "true_false": 2}
    assert split_counts(7, ["mcq", "short", "long"]) == {"mcq": 3, "short": 2, "long": 2}
    assert split_counts(2, ["mcq", "short", "long"]) == {"mcq": 1, "short": 1, "long": 0}


def test_select_meets_type_targets_then_fills_up():
    valid = [check(RawQuestion.model_validate(q)) for q in POOL]
    chosen = select_questions(valid, {"mcq": 1, "true_false": 1, "short": 1}, 5)
    assert len(chosen) == 5
    assert {"mcq", "true_false", "short"} <= {q.type for q in chosen[:3]}


# ---------------------------------------------------------------- orchestration


@pytest.fixture
def ai():
    provider = ScriptedProvider()
    return AIService(provider, Settings(groq_api_key="test"), sleep=lambda _: None), provider


def run(ai_and_provider, *, count=5, types=None, version=1, prior=None, difficulty="mixed", **kw):
    service, _ = ai_and_provider
    return generate(
        service, note_title="Magnets", note_text=NOTE_TEXT, subject="Science", grade=6, chapter_title="Exploring Magnets",
        count=count, types=types or ALL_TYPES, difficulty=difficulty, version=version, prior=prior or [], **kw,
    )


def test_returns_exactly_n_by_asking_for_spares_and_keeping_the_best(ai):
    _, provider = ai
    provider.replies.append(reply(pool(0, 8)))  # the model returns extra
    result = run(ai, count=5)
    assert len(result.questions) == 5 and result.shortfall is None and result.ai_calls == 1
    prompt = provider.calls[0]["messages"][1]["content"]
    assert "Write 7 questions in total" in prompt  # 5 wanted + 2 spares


def test_tops_up_when_the_first_reply_is_short(ai):
    _, provider = ai
    provider.replies += [reply(pool(0, 3)), reply(pool(3, 8))]
    result = run(ai, count=6)
    assert len(result.questions) == 6 and result.ai_calls == 2 and result.shortfall is None
    assert len({q.text for q in result.questions}) == 6


def test_reports_a_shortfall_instead_of_inventing_filler(ai):
    _, provider = ai
    provider.replies += [reply(pool(0, 3)), reply(pool(0, 3))]  # second reply only repeats itself
    result = run(ai, count=8)
    assert len(result.questions) == 3 and result.ai_calls == 2
    assert "only supported 3 good questions (you asked for 8)" in result.shortfall
    assert result.rejected["duplicate"] == 3


def test_model_saying_insufficient_stops_further_calls(ai):
    _, provider = ai
    provider.replies.append(reply(pool(0, 2), insufficient=True))
    result = run(ai, count=8)
    assert result.ai_calls == 1 and len(result.questions) == 2 and result.shortfall


def test_nothing_usable_gives_a_clear_message(ai):
    _, provider = ai
    provider.replies.append(reply([], insufficient=True))
    result = run(ai, count=5)
    assert result.questions == [] and "No good questions" in result.shortfall


def test_questions_that_repeat_earlier_versions_are_rejected(ai):
    _, provider = ai
    earlier = [(q["question"], q["answer"]) for q in pool(0, 5)]
    provider.replies.append(reply(pool(0, 5) + pool(5, 12)))
    result = run(ai, count=5, version=2, prior=earlier)
    assert len(result.questions) == 5
    assert all(q.text not in {e[0] for e in earlier} for q in result.questions)
    assert result.rejected["duplicate"] == 5
    # the earlier questions were shown to the model so it could avoid them
    assert POOL[0]["question"][:40] in provider.calls[0]["messages"][1]["content"]


def test_shortfall_message_blames_earlier_versions_when_there_are_any(ai):
    _, provider = ai
    earlier = [(q["question"], q["answer"]) for q in pool(0, 6)]
    provider.replies += [reply(pool(0, 6)), reply(pool(0, 6))]
    result = run(ai, count=5, version=2, prior=earlier)
    assert result.questions == [] or "differ from your earlier versions" in (result.shortfall or "")
    assert "earlier versions" in result.shortfall or "No good questions" in result.shortfall


def test_ungrounded_questions_never_reach_the_teacher(ai):
    _, provider = ai
    made_up = dict(POOL[0], question="Which metal is used in nuclear reactors?", options=["Plutonium", "Iron", "Glass", "Rubber"], answer="Plutonium")
    provider.replies.append(reply([made_up] + pool(1, 8)))
    result = run(ai, count=5)
    assert all("nuclear" not in q.text for q in result.questions)
    assert result.rejected["answer not found in the note"] == 1


def test_only_requested_types_are_returned(ai):
    _, provider = ai
    provider.replies.append(reply(pool(0, 15)))
    result = run(ai, count=3, types=["mcq"])
    assert {q.type for q in result.questions} == {"mcq"}


def test_explicit_section_choice_is_honoured_including_recaps(ai):
    _, provider = ai
    provider.replies.append(reply(pool(0, 8)))
    run(ai, count=5, section_indices=[3])  # the "Quick Recap" section
    prompt = provider.calls[0]["messages"][1]["content"]
    assert "### Quick Recap" in prompt and "### Magnetic Materials" not in prompt


def test_recap_sections_are_skipped_by_default(ai):
    _, provider = ai
    provider.replies.append(reply(pool(0, 8)))
    run(ai, count=5)
    prompt = provider.calls[0]["messages"][1]["content"]
    assert "### Magnetic Materials" in prompt and "Quick Recap" not in prompt


def test_each_version_has_a_concrete_emphasis(ai):
    _, provider = ai
    for version, phrase in ((1, "Balanced"), (2, "Apply, Analyze or Evaluate"), (3, "Remember or Understand")):
        provider.replies.append(reply(pool(0, 8)))
        run(ai, count=5, version=version)
        assert phrase in provider.calls[-1]["messages"][1]["content"]
    assert "At least 4 of the 7" in provider.calls[1]["messages"][1]["content"]  # numbers, not adjectives


def test_extra_top_ups_stop_when_time_runs_out(ai, monkeypatch):
    _, provider = ai
    monkeypatch.setattr(qg, "TOPUP_TIME_BUDGET_S", -1)
    provider.replies += [reply(pool(0, 2)), reply(pool(2, 8))]
    result = run(ai, count=6)
    assert result.ai_calls == 1 and len(result.questions) == 2 and result.shortfall


def test_the_ai_is_asked_for_json_with_the_schema_and_a_token_cap(ai):
    _, provider = ai
    provider.replies.append(reply(pool(0, 8)))
    run(ai, count=5)
    call = provider.calls[0]
    assert call["json_mode"] and call["max_tokens"] == qg.MAX_OUTPUT_TOKENS
    assert "JSON Schema" in call["messages"][0]["content"]
    assert json.dumps(qg.RawBatch.model_json_schema())[:40] in call["messages"][0]["content"]
