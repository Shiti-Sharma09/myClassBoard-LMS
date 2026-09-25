"""Try the question generator on a sample note and report timing, counts and quality signals.

    python -m scripts.eval_questions                              (10 questions, versions 1 to 3, the 10-page note)
    python -m scripts.eval_questions --note thin_moon_note.txt    (the "too thin" path)
    python -m scripts.eval_questions --versions 1 --show          (print every question)

Makes real AI calls. Reports: seconds per version (target: 10 questions in under 60 s for a 10-page
note), how many questions came back, what code rejected and why, and near-duplicates across versions.
"""

import argparse
import logging
import time
from pathlib import Path

from app.ai import get_ai_service
from app.services.dedupe import is_duplicate
from app.services.extract import extract_text
from app.services.question_gen import QUESTION_TYPES, VERSION_NAMES, generate

NOTES = Path(__file__).resolve().parents[2] / "sample_data" / "notes"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--note", default="exploring_magnets.pdf")
    parser.add_argument("--count", type=int, default=10)
    parser.add_argument("--versions", type=int, default=3)
    parser.add_argument("--difficulty", default="mixed")
    parser.add_argument("--types", default=",".join(QUESTION_TYPES))
    parser.add_argument("--show", action="store_true")
    args = parser.parse_args()
    logging.getLogger("ai").setLevel(logging.WARNING)

    path = NOTES / args.note
    text = extract_text(path.name, path.read_bytes())
    ai = get_ai_service()
    types = args.types.split(",")
    print(f"Note: {path.name} ({len(text.split())} words). Asking for {args.count} questions per version, types {types}\n")

    earlier: list[tuple[str, str]] = []
    for version in range(1, args.versions + 1):
        started = time.perf_counter()
        result = generate(
            ai,
            note_title=path.stem.replace("_", " ").title(),
            note_text=text,
            subject="Science",
            grade=6,
            chapter_title=None,
            count=args.count,
            types=types,
            difficulty=args.difficulty,
            version=version,
            prior=earlier,
        )
        seconds = time.perf_counter() - started
        by_type: dict[str, int] = {}
        for q in result.questions:
            by_type[q.type] = by_type.get(q.type, 0) + 1
        blooms: dict[str, int] = {}
        for q in result.questions:
            blooms[q.bloom] = blooms.get(q.bloom, 0) + 1
        topics = len({q.topic for q in result.questions})
        dupes = sum(1 for q in result.questions if is_duplicate(q.text, q.answer, earlier))
        print(f"Version {version} ({VERSION_NAMES[version]}): {len(result.questions)}/{args.count} questions in {seconds:.1f}s, {result.ai_calls} AI call(s)")
        print(f"  types: {by_type}   bloom: {blooms}   distinct topics: {topics}")
        print(f"  rejected by code: {result.rejected or 'none'}   near-duplicates of earlier versions: {dupes}")
        if args.show:
            for new, old in result.duplicate_pairs:
                print(f"   DUP  new: {new}")
                print(f"        old: {old}")
        if args.show:
            for reason, question, answer in result.rejected_examples:
                print(f"   REJECTED ({reason}): {question} => {answer}")
        if result.shortfall:
            print(f"  SHORTFALL: {result.shortfall}")
        if args.show:
            for i, q in enumerate(result.questions, 1):
                print(f"   {i}. [{q.type}/{q.difficulty}/{q.bloom}/{q.topic}] {q.text}")
                if q.options:
                    print(f"      options: {q.options}")
                print(f"      answer: {q.answer}")
        earlier += [(q.text, q.answer) for q in result.questions]
        print()


if __name__ == "__main__":
    main()
