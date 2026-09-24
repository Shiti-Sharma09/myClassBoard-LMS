import io

import pytest
from PIL import Image

from app.services.extract import ExtractionError, extract_text
from app.services.images import ImageError, MAX_SIDE, pdf_to_images, preprocess
from app.services.ocr import strip_uncertain, suggest_title, uncertain_words


def test_strip_uncertain_keeps_the_words():
    assert strip_uncertain("A [?magnet?] attracts [?iron?].") == "A magnet attracts iron."
    assert strip_uncertain("cannot read [?illegible?] here") == "cannot read [illegible] here"
    assert strip_uncertain("no markers") == "no markers"


def test_uncertain_words_are_listed_in_order():
    assert uncertain_words("a [?b?] c [?d e?]") == ["b", "d e"]


@pytest.mark.parametrize(
    "text, title",
    [
        ("Magnets - Class Notes\n- a", "Magnets - Class Notes"),
        ("\n\n# Water Cycle:\nbody", "Water Cycle"),
        ("- [?Iron?] facts\nmore", "Iron facts"),
        ("   \n  ", "Handwritten note"),
    ],
)
def test_suggested_title(text, title):
    assert suggest_title(text) == title


def _jpeg(size, orientation=None) -> bytes:
    img = Image.new("RGB", size, (200, 200, 200))
    buf = io.BytesIO()
    if orientation:
        exif = Image.Exif()
        exif[274] = orientation
        img.save(buf, "JPEG", exif=exif)
    else:
        img.save(buf, "JPEG")
    return buf.getvalue()


def test_preprocess_shrinks_big_photos():
    out = Image.open(io.BytesIO(preprocess(_jpeg((4000, 3000)))))
    assert max(out.size) == MAX_SIDE


def test_preprocess_does_not_enlarge_small_images():
    assert Image.open(io.BytesIO(preprocess(_jpeg((300, 200))))).size == (300, 200)


def test_preprocess_fixes_phone_rotation():
    # phones store portrait shots as landscape pixels plus an EXIF "rotate" flag
    out = Image.open(io.BytesIO(preprocess(_jpeg((400, 200), orientation=6))))
    assert out.size == (200, 400)


def test_preprocess_rejects_non_images():
    with pytest.raises(ImageError):
        preprocess(b"definitely not an image")


def test_pdf_page_limit_and_bad_pdfs():
    buf = io.BytesIO()
    first = Image.new("RGB", (50, 50), "white")
    first.save(buf, "PDF", save_all=True, append_images=[first.copy() for _ in range(5)])  # 6 pages
    with pytest.raises(ImageError, match="pages or fewer"):
        pdf_to_images(buf.getvalue())
    with pytest.raises(ImageError):
        pdf_to_images(b"%PDF-garbage")


def test_extraction_rejects_unsupported_and_empty_files():
    with pytest.raises(ExtractionError, match="PDF, DOCX or TXT"):
        extract_text("a.png", b"x")
    with pytest.raises(ExtractionError, match="No text"):
        extract_text("a.txt", b"   \n ")
    assert extract_text("a.txt", "café ✓".encode()) == "café ✓"
