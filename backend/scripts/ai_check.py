"""Live smoke test of the AI layer against the real provider.

    python -m scripts.ai_check          (from backend/, with GROQ_API_KEY in ../.env or the environment)
    docker compose run --rm backend python -m scripts.ai_check

Checks the main and fast text models and the vision model. Prints model names, latency
and pass/fail only, never keys or prompt text.
"""

import io
import time

from PIL import Image, ImageDraw, ImageFont
from pydantic import BaseModel

from app.ai import AIError, get_ai_service
from app.config import get_settings


class Ping(BaseModel):
    status: str
    echo: str


class Transcript(BaseModel):
    text: str


def _sample_image() -> bytes:
    img = Image.new("RGB", (900, 160), "white")
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("arial.ttf", 48)
    except OSError:
        font = ImageFont.load_default(48)
    draw.text((24, 44), "Magnets have two poles", fill="black", font=font)
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


def main() -> int:
    settings = get_settings()
    ai = get_ai_service()
    failures = 0

    def check(label: str, model_name: str, fn) -> None:
        nonlocal failures
        started = time.perf_counter()
        try:
            detail = fn()
            print(f"PASS  {label:<7} {model_name:<26} {time.perf_counter() - started:5.2f}s  {detail}")
        except AIError as exc:
            failures += 1
            print(f"FAIL  {label:<7} {model_name:<26} {exc.message}")

    check("main", settings.llm_model_main, lambda: ai.run_json("ping", {"word": "hello"}, Ping, model="main").status)
    check("fast", settings.llm_model_fast, lambda: ai.run_json("ping", {"word": "hello"}, Ping, model="fast").status)
    check(
        "vision",
        settings.vision_model,
        lambda: repr(
            ai.run_json("ocr_check", {}, Transcript, model="vision", images=[(_sample_image(), "image/png")]).text
        ),
    )
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
