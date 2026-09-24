# Sample data

Everything here is **synthetic**. It exists so each module can be demoed and measured without real student material.

Regenerate all of it (deterministic, so the output is identical every time):

```bash
cd backend
python -m scripts.make_sample_data
```

## Typed notes (`notes/`)

Sources are in `source/*.md`. The script turns them into PDF or DOCX.

| File | Format | Size | Used for |
|---|---|---|---|
| `exploring_magnets.pdf` | PDF | 10 pages, about 3,400 words | The "10 questions from a 10-page note in under 60 s" timing test |
| `methods_of_separation.pdf` | PDF | 3 pages | Everyday question-bank demo |
| `states_of_water.docx` | DOCX | 2 pages | Tests DOCX upload |
| `mindful_eating.docx` | DOCX | 1 to 2 pages | Tests DOCX upload |
| `thin_moon_note.txt` | TXT | about 70 words | Deliberately too thin: shows the "this note only supports N good questions" banner |

## Handwritten samples (`handwritten/`)

Pages rendered from free handwriting fonts on ruled paper, then degraded to look like phone photos (tilt, uneven light, blur, noise, JPEG compression).

| File | Style | Font |
|---|---|---|
| `neat_1.jpg`, `neat_3.jpg` | Neat, upright | Patrick Hand |
| `neat_2.jpg` | Neat, rounder | Indie Flower |
| `neat_notes.pdf` | 2-page PDF of `neat_1` and `neat_2` | Tests the PDF upload path |
| `messy_1.jpg` | Scrappy, narrow | Reenie Beanie |
| `messy_2.jpg` | Joined-up cursive, uneven spacing | Homemade Apple |
| `messy_3.jpg` | Loose print | Shadows Into Light |

`handwritten/ground_truth/<name>.txt` holds the exact text on each page. The OCR evaluation compares model output to these files to compute word error rate.

### Read this before quoting an accuracy number

These pages are **easier than real handwriting**: font glyphs are consistent, ink is clean, and there is no smudging, crossing-out or cramped writing. Accuracy on them will be optimistic. The set is also small (about 300 words), so one wrong word moves the score by a third of a percent.

For an honest number, photograph two or three pages of real handwriting with a phone, drop them in `handwritten/` as `real_1.jpg`, `real_2.jpg`, and add a matching `ground_truth/real_1.txt` for each. Report neat, messy and real results separately.

## Fonts

The handwriting fonts (SIL Open Font License and Apache 2.0, from Google Fonts) are downloaded on first run into `sample_data/.fonts/`, which is git-ignored.
