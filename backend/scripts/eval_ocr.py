"""Measures handwriting OCR accuracy against ground-truth text.

    python -m scripts.eval_ocr            (from backend/)
    python -m scripts.eval_ocr --raw      (skip image preprocessing, to see whether it helps)

Compares model output to sample_data/handwritten/ground_truth/<name>.txt for every image
that has ground truth. Reports word error rate (WER) and word accuracy (1 - WER) per file
and per group (neat / messy / real). Group results are what METRICS.md quotes.

Text is normalised before comparing: lower-case, punctuation and bullet dashes removed, the
model's [?uncertain?] markers stripped. Accuracy on the synthetic samples is optimistic
(see sample_data/README.md), so add real photos named real_*.jpg with matching ground truth.
"""

import argparse
import re
import time
from pathlib import Path

import jiwer

from app.ai import get_ai_service
from app.services.images import pdf_to_images, preprocess
from app.services.ocr import read_pages, strip_uncertain

HAND = Path(__file__).resolve().parents[2] / "sample_data" / "handwritten"
TRUTH = HAND / "ground_truth"


def normalise(text: str) -> str:
    text = strip_uncertain(text).lower()
    text = re.sub(r"^\s*[-_•*]\s+", "", text, flags=re.MULTILINE)  # bullet markers
    text = re.sub(r"[^a-z0-9\s]", " ", text)  # punctuation, underscores
    return re.sub(r"\s+", " ", text).strip()


def word_accuracy(reference: str, hypothesis: str) -> tuple[float, int]:
    """Returns (word accuracy 0..1, number of reference words)."""
    ref, hyp = normalise(reference), normalise(hypothesis)
    wer = jiwer.wer(ref, hyp)
    return max(0.0, 1.0 - wer), len(ref.split())


def group_of(name: str) -> str:
    return next((g for g in ("neat", "messy", "real") if name.startswith(g)), "other")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw", action="store_true", help="skip preprocessing")
    parser.add_argument("--show", action="store_true", help="print model output next to the truth")
    args = parser.parse_args()

    ai = get_ai_service()
    results: dict[str, list[tuple[float, int]]] = {}
    files = sorted(p for p in HAND.iterdir() if p.suffix.lower() in {".jpg", ".jpeg", ".png", ".pdf"})
    for path in files:
        truth_file = TRUTH / f"{path.stem}.txt"
        if not truth_file.exists():
            continue
        data = path.read_bytes()
        pages = pdf_to_images(data) if path.suffix.lower() == ".pdf" else [data]
        images = pages if args.raw else [preprocess(p) for p in pages]
        if args.raw:  # still needs to be a size the API accepts
            images = [preprocess(p) if len(p) > 3_000_000 else p for p in pages]
        started = time.perf_counter()
        hypothesis = read_pages(ai, images)
        elapsed = time.perf_counter() - started
        reference = truth_file.read_text(encoding="utf-8")
        accuracy, n_words = word_accuracy(reference, hypothesis)
        results.setdefault(group_of(path.stem), []).append((accuracy, n_words))
        print(f"{path.name:<16} {accuracy * 100:5.1f}% word accuracy   {n_words:3d} words   {elapsed:4.1f}s")
        if args.show:
            print("  truth:", normalise(reference))
            print("  model:", normalise(hypothesis))

    print("\nBy group (weighted by word count):")
    for group, rows in results.items():
        total = sum(n for _, n in rows)
        weighted = sum(a * n for a, n in rows) / total
        print(f"  {group:<6} {weighted * 100:5.1f}%   ({len(rows)} files, {total} words)")


if __name__ == "__main__":
    main()
