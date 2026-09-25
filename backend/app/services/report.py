"""Topic-wise test report. Plain arithmetic over the marked answers, no AI."""

from dataclasses import dataclass

TOP_N = 3


@dataclass(frozen=True)
class Row:
    question_id: int
    topic: str
    text: str
    marks: float
    max_marks: float
    note_id: int | None


def pct(marks: float, max_marks: float) -> int:
    return int(marks / max_marks * 100 + 0.5) if max_marks > 0 else 0


def build_report(rows: list[Row], threshold: int) -> dict:
    """Per-topic scores in the order topics first appear, weak flags, and up to 3 priorities.

    A priority is a topic where marks were lost, worst percentage first (ties: most marks lost).
    `missed` lists exactly the questions on which marks were lost, so the report can be checked against the answers.
    """
    order: list[str] = []
    grouped: dict[str, list[Row]] = {}
    for row in rows:
        if row.topic not in grouped:
            order.append(row.topic)
        grouped.setdefault(row.topic, []).append(row)

    topics = []
    for name in order:
        group = grouped[name]
        got, out_of = sum(r.marks for r in group), sum(r.max_marks for r in group)
        percent = pct(got, out_of)
        topics.append(
            {
                "topic": name,
                "marks": got,
                "max_marks": out_of,
                "percent": percent,
                "weak": percent < threshold,
                "questions": len(group),
                "missed": [{"question_id": r.question_id, "text": r.text} for r in group if r.marks < r.max_marks],
                "note_id": next((r.note_id for r in group if r.note_id is not None), None),
            }
        )

    losing = [t for t in topics if t["missed"]]
    priorities = sorted(losing, key=lambda t: (t["percent"], -(t["max_marks"] - t["marks"]), t["topic"]))[:TOP_N]
    total, out_of = sum(r.marks for r in rows), sum(r.max_marks for r in rows)
    return {"marks": total, "max_marks": out_of, "percent": pct(total, out_of), "topics": topics, "priorities": priorities}
