"""Image preparation for handwriting OCR.

Deliberately light: fix phone rotation, lift contrast, sharpen a little, and shrink to a
size the vision model handles well. Heavy filtering (binarising, aggressive denoising) can
make vision models worse, so add steps only when the accuracy numbers say they help.
"""

import io

import pymupdf
from PIL import Image, ImageFilter, ImageOps, UnidentifiedImageError

MAX_SIDE = 1400  # image token cost is fixed per page, so smaller only saves upload size
MAX_PDF_PAGES = 5  # free tier allows about 3 pages/minute (8k tokens per minute)


class ImageError(Exception):
    """Raised with a message that is safe to show to the user."""


def preprocess(data: bytes) -> bytes:
    """Returns a cleaned-up JPEG of the page."""
    try:
        with Image.open(io.BytesIO(data)) as raw:
            img = ImageOps.exif_transpose(raw).convert("RGB")
    except (UnidentifiedImageError, OSError):
        raise ImageError("That file doesn't look like a valid image.") from None
    img = ImageOps.autocontrast(img, cutoff=1)
    img = img.filter(ImageFilter.UnsharpMask(radius=1.5, percent=60, threshold=3))
    scale = MAX_SIDE / max(img.size)
    if scale < 1:
        img = img.resize((round(img.width * scale), round(img.height * scale)), Image.LANCZOS)
    out = io.BytesIO()
    img.save(out, "JPEG", quality=85)
    return out.getvalue()


def pdf_to_images(data: bytes) -> list[bytes]:
    """Renders each PDF page to a PNG. Used for scanned or photographed handwritten PDFs."""
    try:
        with pymupdf.open(stream=data, filetype="pdf") as doc:
            if doc.page_count > MAX_PDF_PAGES:
                raise ImageError(f"That PDF has {doc.page_count} pages. Please upload {MAX_PDF_PAGES} pages or fewer at a time.")
            return [page.get_pixmap(dpi=150).tobytes("png") for page in doc]
    except ImageError:
        raise
    except Exception:
        raise ImageError("That PDF couldn't be opened.") from None
