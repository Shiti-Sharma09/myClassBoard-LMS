"""Cheap near-duplicate detection for questions. No embeddings: word overlap is enough to catch
"the same question re-worded a little", which is what a regenerated version tends to produce.

Two measures must agree, because each alone misfires:
  * containment (share of the smaller question's words found in the other) catches a short question
    that sits inside a longer one, but wrongly flags a short statement that merely shares a few words;
  * Jaccard (shared words over all words) is stricter, so it stops those false alarms.

It will miss a truly different wording of the same idea. Refresh quality also relies on each version
reading a different part of the note and on the model being shown the earlier questions to avoid.
"""

import re

_STOP = frozenset(
    "a an the of to in on at is are was were be been being and or but if then than that this these those "
    "it its as by for from with which what who whom whose when where why how do does did has have had can "
    "could should would will may might must not no yes true false following correct answer question".split()
)
_WORD = re.compile(r"[a-z0-9]+")
_BLANK = re.compile(r"_{2,}")

SIMILAR = 0.6  # containment at or above this...
MIN_JACCARD = 0.4  # ...and Jaccard at or above this, sharing at least MIN_SHARED words, means "the same question"
MIN_SHARED = 3
SAME_ANSWER_SIMILAR = 0.4  # with the same answer, a little less overlap is enough
SAME_ANSWER_JACCARD = 0.3


def tokens(text: str) -> frozenset[str]:
    words = _WORD.findall(_BLANK.sub(" ", text.lower()))
    return frozenset(w[:-1] if len(w) > 3 and w.endswith("s") else w for w in words if w not in _STOP)


def overlap(a: frozenset[str], b: frozenset[str]) -> float:
    """Share of the smaller question's words found in the other (0 to 1).

    With fewer than 3 meaningful words this is unreliable ("What is a magnet?" is 100% inside every
    magnet question), so it falls back to Jaccard.
    """
    if not a or not b:
        return 0.0
    shared = len(a & b)
    if min(len(a), len(b)) < 3:
        return shared / len(a | b)
    return shared / min(len(a), len(b))


def jaccard(a: frozenset[str], b: frozenset[str]) -> float:
    return len(a & b) / len(a | b) if a and b else 0.0


def find_duplicate(text: str, answer: str, others: list[tuple[str, str]]) -> str | None:
    """The text of the first question in `others` that (text, answer) near-copies, or None."""
    t, a = tokens(text), tokens(answer)
    for other_text, other_answer in others:
        o_t = tokens(other_text)
        contained, jac = overlap(t, o_t), jaccard(t, o_t)
        if contained >= SIMILAR and jac >= MIN_JACCARD and len(t & o_t) >= MIN_SHARED:
            return other_text
        if contained >= SAME_ANSWER_SIMILAR and jac >= SAME_ANSWER_JACCARD and a and a == tokens(other_answer):
            return other_text
    return None


def is_duplicate(text: str, answer: str, others: list[tuple[str, str]]) -> bool:
    return find_duplicate(text, answer, others) is not None
