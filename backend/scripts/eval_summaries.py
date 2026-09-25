"""Try the parent-summary narrator on the seeded students and report how often the number check had to step in.

    python -m scripts.eval_summaries                 (every student in the demo school)
    python -m scripts.eval_summaries --limit 4 --show

Makes real AI calls (about 4 to 5 students a minute on the free tier). Uses a throwaway in-memory database, so
it never touches your data. Reports, per student: overall %, source (ai or template), rejected attempts.
The figure that matters for METRICS.md is "numbers not in the facts" after verification: it must be 0.
"""

import argparse
import logging
import sys
import time

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.ai import get_ai_service
from app.models import Base, Student
from app.routers.summaries import _records
from app.seed.seed import seed_database
from app.services.metrics import compute_facts
from app.services.summary import narrate, problems


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--show", action="store_true")
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    logging.getLogger("ai").setLevel(logging.WARNING)

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    ai = get_ai_service()
    rows = []
    with Session(engine) as db:
        seed_database(db)
        students = db.scalars(select(Student).order_by(Student.id)).all()
        for student in students[: args.limit or None]:
            facts = compute_facts(_records(db, student.id), 60)
            started = time.perf_counter()
            result = narrate(ai, facts, student.user.name)
            seconds = time.perf_counter() - started
            leftover = problems(result.narrative, facts)
            rows.append((student.user.name, student.persona, facts["overall_percent"], result.source, result.verify_failures, len(leftover), seconds))
            print(f"{student.user.name:<16}{student.persona:<10}{facts['overall_percent']:>4}%  {result.source:<9}rejected={result.verify_failures}  remaining_problems={len(leftover)}  {seconds:4.1f}s")
            if result.rejected_reasons:
                print("    rejected because:", result.rejected_reasons)
            if args.show:
                n = result.narrative
                print("   ", n.overall, "\n    Trend:", n.trend, "\n    Strengths:", n.strengths, "\n    Work on:", n.areas_to_work_on, "\n    Tips:", n.home_tips, "\n")

    total = len(rows)
    ai_used = sum(r[3] == "ai" for r in rows)
    print(f"\n{total} summaries: {ai_used} written by the model, {total - ai_used} fell back to the template")
    print(f"Attempts rejected by the number check: {sum(r[4] for r in rows)} (each one was retried or replaced)")
    print(f"Wrong numbers or ranking language shown to a teacher: {sum(r[5] for r in rows)} (must be 0)")
    print(f"Average time per student: {sum(r[6] for r in rows) / max(total, 1):.1f}s")


if __name__ == "__main__":
    main()
