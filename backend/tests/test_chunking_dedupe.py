import pytest

from app.services.chunking import Section, build_context, split_sections
from app.services.dedupe import find_duplicate, is_duplicate, tokens

# ---------------------------------------------------------------- sections

INTRO = "A magnet attracts iron. Magnets are used in many places around the house, from doors to toys and compasses. " * 3
POLES = "Every magnet has two poles. The north pole points north when the magnet hangs freely. The south pole points the other way. " * 3
USES = "Compasses show direction. Fridge doors stay shut. Cranes lift scrap iron in factories and junkyards across the world. " * 3
NOTE = f"""Exploring Magnets

Class 6 Science

1. Introduction

{INTRO}

2. Poles of a Magnet

{POLES}

3. Uses of Magnets

{USES}
"""


def test_headings_become_sections():
    sections = split_sections(NOTE, "Exploring Magnets")
    titles = [s.title for s in sections]
    assert "Introduction" in titles and "Poles of a Magnet" in titles and "Uses of Magnets" in titles
    poles = next(s for s in sections if s.title == "Poles of a Magnet")
    assert "two poles" in poles.text and "Compasses" not in poles.text
    assert "Exploring Magnets" not in titles  # the title/subtitle preamble is folded into the first section
    assert "Class 6 Science" in sections[0].text
    assert [s.index for s in sections] == list(range(len(sections)))


def test_numbered_sentences_are_not_headings():
    text = "1. Filter the mixture. The sand stays behind on the paper.\n2. Heat the water until only salt is left in the dish.\n" + "More words here. " * 30
    assert len(split_sections(text, "Steps")) >= 1
    assert all("Filter the mixture" not in s.title for s in split_sections(text, "Steps"))


def test_no_headings_falls_back_to_parts():
    text = "\n\n".join(f"Paragraph {i}. " + "words " * 200 for i in range(6))
    sections = split_sections(text, "Untitled")
    assert len(sections) >= 2 and sections[0].title.startswith("Part")
    assert all(s.text.strip() for s in sections)


def test_tiny_sections_are_folded_into_the_previous_one():
    text = "1. Big Topic\n\n" + "Real content here. " * 40 + "\n\n2. Tiny\n\nJust a line.\n"
    sections = split_sections(text, "T")
    assert len(sections) == 1 and "Just a line" in sections[0].text


def test_huge_sections_are_split_and_labelled():
    text = "1. Long Topic\n\n" + "\n\n".join("A paragraph of text about the topic. " * 30 for _ in range(12))
    sections = split_sections(text, "T")
    assert len(sections) >= 2 and "(part 2)" in sections[1].title
    assert all(len(s.text) <= 5200 for s in sections)


# ---------------------------------------------------------------- context windows


def big_note(n_sections=12, words=220) -> list[Section]:
    return [Section(i, f"Topic {i}", " ".join(f"s{i}w{j}." if j % 12 else f"s{i}w{j}. " for j in range(words))) for i in range(n_sections)]


def test_small_note_is_sent_whole_to_every_version():
    sections = [Section(0, "A", "Short text."), Section(1, "B", "More short text.")]
    for v in (1, 2, 3):
        assert build_context(sections, 11_000, v) == sections


def test_big_note_stays_within_budget_for_every_version():
    sections = big_note()
    for v in (1, 2, 3):
        ctx = build_context(sections, 5_000, v)
        assert 0 < sum(len(s.text) for s in ctx) <= 5_000


def test_versions_read_different_parts_of_a_big_note():
    sections = [Section(i, f"T{i}", " ".join(f"Fact{i}x{j} is stated here." for j in range(60))) for i in range(9)]
    seen = []
    for v in (1, 2, 3):
        words = {w for s in build_context(sections, 6_000, v) for w in s.text.split() if w.startswith("Fact")}
        seen.append(words)
    assert not (seen[0] & seen[1]) and not (seen[0] & seen[2]) and not (seen[1] & seen[2])
    assert all(seen)


def test_context_keeps_section_titles_and_order():
    ctx = build_context(big_note(), 5_000, 2)
    assert [s.index for s in ctx] == sorted(s.index for s in ctx)
    assert all(s.title == f"Topic {s.index}" for s in ctx)


def test_empty_input_is_safe():
    assert build_context([], 1000) == []


# ---------------------------------------------------------------- duplicates


def test_rewording_the_same_question_is_a_duplicate():
    old = [("What happens when the north pole of one magnet is brought near the south pole of another?", "They attract")]
    assert is_duplicate("What happens when the south pole of a magnet is brought near the north pole of another magnet?", "They attract each other", old)


def test_different_questions_are_not_duplicates():
    old = [("Which materials does a magnet attract?", "Iron")]
    assert not is_duplicate("Name the instrument used to find directions.", "A compass", old)


def test_same_answer_with_moderate_overlap_counts():
    old = [("The space around a magnet where its force can be felt is called the _____ .", "magnetic field")]
    assert is_duplicate("What is the region around a magnet where its force acts called?", "magnetic field", old)


def test_blanks_and_stopwords_do_not_count_as_words():
    assert tokens("The _____ of a magnet is the ______") == tokens("magnet")


def test_very_short_questions_do_not_match_everything():
    old = [("Describe how a magnet attracts iron, nickel and cobalt in an experiment.", "x")]
    # one meaningful word ("magnet") is fully contained in the long question, but that is not a repeat
    assert not is_duplicate("What is a magnet?", "An object that attracts iron", old)


def test_short_statement_sharing_a_few_words_is_not_a_duplicate():
    # regression: scored 0.6 on containment alone, but these are clearly different questions
    old = [("Every magnet has exactly two poles.", "True")]
    assert not is_duplicate("What happens when unlike poles of two magnets come close?", "They attract", old)


@pytest.mark.parametrize(
    "new, new_answer, old, old_answer",
    [
        ("Copper is strongly attracted by a magnet.", "False", "Which of these materials is attracted by a magnet?", "Iron"),
        ("Two like poles of magnets _____ each other.", "repel", "Every magnet has exactly two poles.", "True"),
    ],
)
def test_short_questions_on_the_same_topic_with_different_answers_are_not_duplicates(new, new_answer, old, old_answer):
    assert not is_duplicate(new, new_answer, [(old, old_answer)])


def test_the_same_fact_asked_two_ways_is_still_caught():
    old = [("Which of the following actions will cause a magnet to lose its strength?", "Heating it strongly")]
    assert is_duplicate("Which of the following actions would most likely reduce the strength of a permanent magnet?", "Heating it strongly", old)
    old = [("A natural magnet is also called a _____ .", "lodestone")]
    assert is_duplicate("Natural magnets are also called _____ .", "lodestone", old)


def test_find_duplicate_returns_the_matching_text():
    old = [("Unrelated question about water.", "a"), ("Which materials are magnetic in nature and attracted?", "iron")]
    assert find_duplicate("Which materials are magnetic in nature?", "iron", old) == old[1][0]
    assert find_duplicate("Something completely different about the moon.", "x", old) is None


@pytest.mark.parametrize("text", ["", "the of and", "___"])
def test_empty_questions_are_never_duplicates(text):
    assert not is_duplicate(text, "", [("Which materials are magnetic?", "iron")])
