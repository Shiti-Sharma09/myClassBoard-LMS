"""Builds the synthetic sample files under sample_data/.

    python -m scripts.make_sample_data          (from backend/)

Typed notes:      sample_data/source/*.md  ->  sample_data/notes/*.pdf and *.docx
Handwritten:      sample_data/handwritten/ground_truth/*.txt  ->  *.jpg (+ one PDF)

The handwriting images are rendered from free handwriting fonts and then degraded
(tilt, uneven light, blur, noise, JPEG) to look like phone photos. They are EASIER to
read than real handwriting, so accuracy measured on them is optimistic. Add a few real
photos to sample_data/handwritten/ for an honest number. Output is deterministic.
"""

import random
import re
import urllib.request
from pathlib import Path

import pymupdf
from docx import Document
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "sample_data"
SOURCE = DATA / "source"
NOTES = DATA / "notes"
HAND = DATA / "handwritten"
TRUTH = HAND / "ground_truth"
FONT_DIR = DATA / ".fonts"

FONT_URLS = {
    "PatrickHand-Regular.ttf": "ofl/patrickhand/PatrickHand-Regular.ttf",
    "IndieFlower-Regular.ttf": "ofl/indieflower/IndieFlower-Regular.ttf",
    "ReenieBeanie.ttf": "ofl/reeniebeanie/ReenieBeanie.ttf",
    "HomemadeApple-Regular.ttf": "apache/homemadeapple/HomemadeApple-Regular.ttf",
    "ShadowsIntoLight.ttf": "ofl/shadowsintolight/ShadowsIntoLight.ttf",
}

# --------------------------------------------------------------------------- typed notes


def parse_markdown(text: str) -> list[tuple[str, str]]:
    """Tiny markdown subset: '# ', '## ', '- ' bullets, blank-line separated paragraphs."""
    blocks: list[tuple[str, str]] = []
    for line in text.splitlines():
        line = line.rstrip()
        if not line:
            continue
        if line.startswith("## "):
            blocks.append(("h2", line[3:]))
        elif line.startswith("# "):
            blocks.append(("h1", line[2:]))
        elif line.startswith("- "):
            blocks.append(("li", line[2:]))
        else:
            blocks.append(("p", line))
    return blocks


def _esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def write_pdf(blocks: list[tuple[str, str]], path: Path, font_pt: float) -> int:
    html, in_list = [], False
    for kind, text in blocks:
        if kind != "li" and in_list:
            html.append("</ul>")
            in_list = False
        if kind == "li" and not in_list:
            html.append("<ul>")
            in_list = True
        tag = {"h1": "h1", "h2": "h2", "p": "p", "li": "li"}[kind]
        html.append(f"<{tag}>{_esc(text)}</{tag}>")
    if in_list:
        html.append("</ul>")
    css = f"""
        body {{ font-family: sans-serif; font-size: {font_pt}pt; line-height: 1.55; color: #1a1a1a; }}
        h1 {{ font-size: 22pt; margin-bottom: 4pt; color: #2b2f8f; }}
        h2 {{ font-size: {font_pt + 3}pt; margin-top: 14pt; margin-bottom: 2pt; color: #2b2f8f; }}
        p  {{ margin-top: 0; margin-bottom: 7pt; }}
        li {{ margin-bottom: 3pt; }}
    """
    page = pymupdf.paper_rect("a4")
    where = page + (56, 56, -56, -56)
    writer = pymupdf.DocumentWriter(str(path))
    story = pymupdf.Story(html="".join(html), user_css=css)
    more = 1
    while more:
        device = writer.begin_page(page)
        more, _ = story.place(where)
        story.draw(device)
        writer.end_page()
    writer.close()
    with pymupdf.open(path) as doc:
        return doc.page_count


def write_docx(blocks: list[tuple[str, str]], path: Path) -> None:
    doc = Document()
    for kind, text in blocks:
        if kind == "h1":
            doc.add_heading(text, level=0)
        elif kind == "h2":
            doc.add_heading(text, level=1)
        elif kind == "li":
            doc.add_paragraph(text, style="List Bullet")
        else:
            doc.add_paragraph(text)
    doc.save(path)


def build_typed_notes() -> None:
    plan = [
        ("exploring_magnets", "pdf", 12.5),  # the long one: aims for about 10 pages
        ("states_of_water", "docx", 0),
        ("methods_of_separation", "pdf", 12.5),
        ("mindful_eating", "docx", 0),
    ]
    for name, fmt, pt in plan:
        blocks = parse_markdown((SOURCE / f"{name}.md").read_text(encoding="utf-8"))
        out = NOTES / f"{name}.{fmt}"
        if fmt == "pdf":
            pages = write_pdf(blocks, out, pt)
            words = sum(len(t.split()) for _, t in blocks)
            print(f"  {out.name}: {pages} pages, {words} words")
        else:
            write_docx(blocks, out)
            print(f"  {out.name}")


# --------------------------------------------------------------------------- handwriting

W, H = 1240, 1754  # A4 at about 150 dpi
LEFT, RIGHT, TOP, LINE_H = 200, 1170, 210, 78


def ensure_fonts() -> None:
    FONT_DIR.mkdir(parents=True, exist_ok=True)
    for filename, path in FONT_URLS.items():
        target = FONT_DIR / filename
        if not target.exists():
            print(f"  downloading {filename}")
            urllib.request.urlretrieve(f"https://raw.githubusercontent.com/google/fonts/main/{path}", target)


def wrap(words: list[str], font: ImageFont.FreeTypeFont, max_width: int) -> list[list[str]]:
    lines: list[list[str]] = [[]]
    for word in words:
        trial = " ".join(lines[-1] + [word])
        if lines[-1] and font.getlength(trial) > max_width:
            lines.append([word])
        else:
            lines[-1].append(word)
    return lines


def ruled_paper(rng: random.Random) -> Image.Image:
    img = Image.new("RGB", (W, H), (251, 249, 241))
    d = ImageDraw.Draw(img)
    for y in range(TOP + 22, H - 90, LINE_H):
        d.line([(0, y), (W, y)], fill=(178, 198, 224), width=2)
    d.line([(LEFT - 40, 0), (LEFT - 40, H)], fill=(226, 140, 140), width=3)
    return img


def render_page(text: str, font_file: str, size: int, ink: tuple, messy: bool, rng: random.Random) -> Image.Image:
    page = ruled_paper(rng)
    font = ImageFont.truetype(str(FONT_DIR / font_file), size)
    y = TOP
    for para_index, raw in enumerate(text.strip().splitlines()):
        is_bullet = raw.startswith("- ")
        is_heading = para_index == 0
        body = raw[2:] if is_bullet else raw
        indent = 46 if is_bullet else 0
        lines = wrap(body.split(), font, RIGHT - LEFT - indent)
        for li, words in enumerate(lines):
            x = LEFT + (indent if is_bullet else 0) + (rng.uniform(-6, 10) if messy else rng.uniform(-2, 4))
            baseline_drift = rng.uniform(-7, 7) if messy else rng.uniform(-2, 2)
            if is_bullet and li == 0:
                mid = y + baseline_drift + size * 0.62
                ImageDraw.Draw(page).line([(LEFT + 4, mid), (LEFT + 26, mid + rng.uniform(-2, 2))], fill=ink, width=4)
            for word in words:
                angle = rng.uniform(-5, 5) if messy else rng.uniform(-1.5, 1.5)
                jitter_y = baseline_drift + (rng.uniform(-6, 6) if messy else rng.uniform(-1.5, 1.5))
                scale = rng.uniform(0.9, 1.1) if messy else 1.0
                f = font if scale == 1.0 else ImageFont.truetype(str(FONT_DIR / font_file), int(size * scale))
                _stamp(page, word, f, (x, y + jitter_y), ink, angle, rng)
                x += f.getlength(word + " ") + (rng.uniform(8, 22) if messy else rng.uniform(0, 3))
            y += LINE_H
        if is_heading:
            ImageDraw.Draw(page).line([(LEFT, y - 22), (LEFT + 520, y - 22 + (rng.uniform(-5, 5) if messy else 0))], fill=ink, width=3)
    return page


def _stamp(page: Image.Image, word: str, font, xy, ink, angle: float, rng: random.Random) -> None:
    """Draw one word on a transparent layer, rotate it slightly, paste it onto the page."""
    bbox = font.getbbox(word)
    w, h = bbox[2] - bbox[0] + 40, bbox[3] - bbox[1] + 60
    layer = Image.new("L", (w, h), 0)
    ImageDraw.Draw(layer).text((20 - bbox[0], 30 - bbox[1]), word, font=font, fill=255)
    if angle:
        layer = layer.rotate(angle, resample=Image.BICUBIC, expand=True)
    colour = Image.new("RGB", layer.size, ink)
    page.paste(colour, (int(xy[0]) - 20, int(xy[1]) - 30), layer)


def light_gradient(size: tuple[int, int], low: int, rng: random.Random) -> Image.Image:
    """Smooth brightness ramp (low..255) in a random direction, like uneven room light."""
    w, h = size
    d = int((w * w + h * h) ** 0.5) + 2  # big enough that the rotated square still covers w x h
    ramp = Image.linear_gradient("L").resize((d, d)).rotate(rng.uniform(0, 360), resample=Image.BICUBIC)
    left, top = (d - w) // 2, (d - h) // 2
    ramp = ramp.crop((left, top, left + w, top + h))
    return ramp.point(lambda v: int(low + (255 - low) * (v / 255)))


def phone_photo(page: Image.Image, messy: bool, rng: random.Random) -> Image.Image:
    """Make a clean page look like a photo: tilt, desk edges, uneven light, blur, noise, JPEG."""
    desk = (92, 84, 76) if messy else (118, 110, 100)
    tilt = rng.uniform(-4.0, 4.0) if messy else rng.uniform(-1.6, 1.6)
    img = page.rotate(tilt, resample=Image.BICUBIC, expand=True, fillcolor=desk)
    # uneven lighting: darker toward one corner
    low = 150 if messy else 195
    shade = light_gradient(img.size, low, rng)
    img = Image.composite(img, Image.new("RGB", img.size, (0, 0, 0)), shade)
    img = img.filter(ImageFilter.GaussianBlur(1.1 if messy else 0.6))
    noise = Image.effect_noise(img.size, 14 if messy else 6).convert("RGB")
    img = Image.blend(img, noise, 0.06 if messy else 0.03)
    scale = 1500 / max(img.size)
    return img.resize((int(img.width * scale), int(img.height * scale)), Image.LANCZOS)


HAND_PLAN = [
    # name,      font,                         size, ink,            messy
    ("neat_1", "PatrickHand-Regular.ttf", 52, (28, 38, 110), False),
    ("neat_2", "IndieFlower-Regular.ttf", 46, (20, 20, 20), False),
    ("neat_3", "PatrickHand-Regular.ttf", 52, (28, 38, 110), False),
    ("messy_1", "ReenieBeanie.ttf", 70, (60, 60, 64), True),
    ("messy_2", "HomemadeApple-Regular.ttf", 36, (40, 45, 90), True),
    ("messy_3", "ShadowsIntoLight.ttf", 54, (55, 55, 55), True),
]


def build_handwritten() -> None:
    ensure_fonts()
    clean_pages: dict[str, Image.Image] = {}
    for i, (name, font_file, size, ink, messy) in enumerate(HAND_PLAN):
        rng = random.Random(1000 + i)
        text = (TRUTH / f"{name}.txt").read_text(encoding="utf-8")
        photo = phone_photo(render_page(text, font_file, size, ink, messy, rng), messy, rng)
        photo.save(HAND / f"{name}.jpg", "JPEG", quality=68 if messy else 85)
        clean_pages[name] = photo
        print(f"  {name}.jpg ({'messy' if messy else 'neat'}, {font_file.split('-')[0].split('.')[0]})")

    # A 2-page PDF of neat pages, to test the PDF upload path.
    pages = [clean_pages["neat_1"].convert("RGB"), clean_pages["neat_2"].convert("RGB")]
    pages[0].save(HAND / "neat_notes.pdf", save_all=True, append_images=pages[1:], resolution=150)
    combined = "\n\n".join((TRUTH / f"{n}.txt").read_text(encoding="utf-8").strip() for n in ("neat_1", "neat_2"))
    (TRUTH / "neat_notes.txt").write_text(combined + "\n", encoding="utf-8")
    print("  neat_notes.pdf (2 pages)")


def main() -> None:
    NOTES.mkdir(parents=True, exist_ok=True)
    print("Typed notes:")
    build_typed_notes()
    print("Handwritten samples:")
    build_handwritten()
    print(f"Done. Files are in {DATA.relative_to(ROOT)}/")


if __name__ == "__main__":
    main()
