"""Handwriting OCR with a vision model.

Vision models don't give per-word confidence scores, so the model is asked to wrap words it
is unsure about as [?word?]. That is self-reported and imperfect: it powers the highlighting on
the review screen, and the human correction step is what keeps the output trustworthy.
"""

import re

from pydantic import BaseModel

from app.ai import AIService

UNCERTAIN = re.compile(r"\[\?(.+?)\?\]")


class OcrPage(BaseModel):
    text: str


def read_pages(ai: AIService, images: list[bytes]) -> str:
    """OCR each page image (already preprocessed JPEGs) in order and join them.

    Sequential on purpose: a page costs about 2,100 tokens and the free tier allows 8,000
    per minute, so parallel calls just trigger rate limits. The AI layer waits and retries.
    """
    total = len(images)
    texts = []
    for number, image in enumerate(images, start=1):
        result = ai.run_json(
            "ocr_page",
            {"n": number, "total": total},
            OcrPage,
            model="vision",
            images=[(image, "image/jpeg")],
            temperature=0.0,  # transcription should be repeatable
        )
        texts.append(result.text.strip())
    return "\n\n".join(t for t in texts if t)


def strip_uncertain(text: str) -> str:
    """Remove the [?word?] markers, keeping the words: `[?magnet?]` -> `magnet`."""
    return UNCERTAIN.sub(lambda m: "[illegible]" if m.group(1).strip().lower() == "illegible" else m.group(1), text)


def uncertain_words(text: str) -> list[str]:
    return [m.group(1) for m in UNCERTAIN.finditer(text)]


def suggest_title(text: str) -> str:
    """First non-empty line, cleaned up, as a default note title."""
    for line in strip_uncertain(text).splitlines():
        cleaned = re.sub(r"^[\s#\-•*]+", "", line).strip(" :")
        if cleaned:
            return cleaned[:80]
    return "Handwritten note"
