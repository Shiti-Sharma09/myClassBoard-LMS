"""Parent Summary numbers. Plain arithmetic, no AI: the model only ever narrates what is computed here.

Every percentage is rounded to a whole number once, here, so the same figure appears everywhere
(charts, narrative, verifier) and a parent can check it against the school report.
"""

from dataclasses import dataclass
from datetime import date

TREND_MIN_CHANGE = 5  # points; a smaller change between early and recent tests counts as "steady"
TOP_N = 3


@dataclass(frozen=True)
class Record:
    topic: str
    chapter: str
    test_name: str
    test_date: date
    marks: float
    max_marks: float


def pct(marks: float, max_marks: float) -> int:
    """Whole-number percentage, rounding halves up (Python's round() would round 12.5 down to 12)."""
    return int(marks / max_marks * 100 + 0.5) if max_marks > 0 else 0


def _group(records: list[Record], key) -> dict:
    groups: dict = {}
    for r in records:
        groups.setdefault(key(r), []).append(r)
    return groups


def _percent(records: list[Record]) -> int:
    return pct(sum(r.marks for r in records), sum(r.max_marks for r in records))


def classify_trend(test_percents: list[int]) -> tuple[str, int | None, int | None]:
    """(trend, earlier average, recent average) from test percentages in date order.

    With 4 or more tests the first two are compared with the last two, which smooths out one bad day;
    with 2 or 3 tests the first is compared with the last; with fewer there is no trend to report.
    """
    if len(test_percents) < 2:
        return "not_enough_data", None, None
    span = 2 if len(test_percents) >= 4 else 1
    early = pct(sum(test_percents[:span]), 100 * span)
    recent = pct(sum(test_percents[-span:]), 100 * span)
    if recent - early >= TREND_MIN_CHANGE:
        return "improving", early, recent
    if early - recent >= TREND_MIN_CHANGE:
        return "declining", early, recent
    return "steady", early, recent


def compute_facts(records: list[Record], threshold: int) -> dict | None:
    """Everything a summary may say, or None when the student has no marks at all."""
    if not records:
        return None

    by_test = sorted(_group(records, lambda r: (r.test_date, r.test_name)).items())
    tests = [{"name": name, "date": d.isoformat(), "percent": _percent(rows)} for (d, name), rows in by_test]

    by_chapter = _group(records, lambda r: r.chapter)
    first_seen = {c: min(r.test_date for r in rows) for c, rows in by_chapter.items()}
    chapters = [{"chapter": c, "percent": _percent(by_chapter[c])} for c in sorted(by_chapter, key=lambda c: first_seen[c])]

    by_topic = _group(records, lambda r: (r.chapter, r.topic))
    topics = [{"topic": t, "chapter": c, "percent": _percent(rows)} for (c, t), rows in sorted(by_topic.items())]
    ranked = sorted(topics, key=lambda t: (t["percent"], t["topic"]))  # weakest first, ties by name

    trend, early, recent = classify_trend([t["percent"] for t in tests])
    weak = [{"topic": t["topic"], "chapter": t["chapter"], "percent": t["percent"]} for t in ranked if t["percent"] < threshold]
    strong = [t for t in reversed(ranked) if t["percent"] >= threshold][:TOP_N]

    return {
        "tests_count": len(tests),
        "overall_percent": _percent(records),
        "weak_threshold": threshold,
        "trend": trend,
        "trend_from": early,
        "trend_to": recent,
        "tests": tests,
        "chapters": chapters,
        "topics": topics,
        "strongest": [{"topic": t["topic"], "percent": t["percent"]} for t in strong],
        "weak_topics": weak,
    }
