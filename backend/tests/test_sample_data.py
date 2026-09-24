"""Guards the sample files the demo and the metrics depend on."""

from pathlib import Path

import pymupdf
import pytest
from docx import Document
from PIL import Image

DATA = Path(__file__).resolve().parents[2] / "sample_data"
HAND = DATA / "handwritten"


def test_long_note_is_ten_pages_for_the_timing_benchmark():
    with pymupdf.open(DATA / "notes" / "exploring_magnets.pdf") as doc:
        text = "".join(page.get_text() for page in doc)
        assert doc.page_count == 10
    assert len(text.split()) > 3000
    assert "Like poles repel" in text  # text is extractable, not an image


def test_docx_notes_are_readable():
    for name in ("states_of_water", "mindful_eating"):
        doc = Document(DATA / "notes" / f"{name}.docx")
        assert len(doc.paragraphs) > 10


def test_thin_note_is_really_thin():
    assert len((DATA / "notes" / "thin_moon_note.txt").read_text().split()) < 100


@pytest.mark.parametrize("name", ["neat_1", "neat_2", "neat_3", "messy_1", "messy_2", "messy_3"])
def test_each_handwritten_image_has_ground_truth(name):
    with Image.open(HAND / f"{name}.jpg") as img:
        assert img.width >= 1000 and img.height >= 1000
    truth = (HAND / "ground_truth" / f"{name}.txt").read_text().strip()
    assert 30 < len(truth.split()) < 200


def test_handwritten_pdf_has_two_pages_and_matching_truth():
    with pymupdf.open(HAND / "neat_notes.pdf") as doc:
        assert doc.page_count == 2
    combined = (HAND / "ground_truth" / "neat_notes.txt").read_text()
    for part in ("neat_1", "neat_2"):
        assert (HAND / "ground_truth" / f"{part}.txt").read_text().strip() in combined
