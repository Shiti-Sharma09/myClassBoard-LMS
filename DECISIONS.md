# Decisions

A running log of choices made while building, and why. Newest at the bottom of each section.

## Scope and process

- **Five modules**, from combining the two source documents: Question Bank, OCR + Notes Library, Assessment (lite), Parent Summary, Interview Bot. Assessment and Parent Summary are deliberately unrelated: Parent Summary reads seeded school marks (`score_records`), Assessment reads in-app attempts.
- **Class 6 CBSE Science only**, 15 synthetic students, 2 classes.
- **One PR per block**, squash-merged, Conventional Commits. See the README's Git workflow section.

## AI provider

- **Groq free tier** for everything AI, because the POC must cost nothing. Model names are config (`.env`), never code.
- Models chosen after probing the account's model list and testing each call live:
  - `openai/gpt-oss-120b` (main): questions, summaries, reports
  - `openai/gpt-oss-20b` (fast): interview turns
  - `qwen/qwen3.8-27b` (vision): handwriting OCR. The gpt-oss models do not accept images.
- `reasoning_effort` is set to `low` for the gpt-oss models to keep latency down.
- We call Groq's OpenAI-compatible HTTP API through `httpx` rather than an SDK: one fewer dependency, and the provider stays a 60-line class behind the `ChatProvider` protocol.
- **Prompts and replies are never logged**, only prompt name, model, token counts and latency, because they can contain student text.

## Backend

- **No migrations.** Tables are created on startup and the demo school is seeded if the database is empty. "Reset demo data" drops and reseeds. Fine for a POC, wrong for anything real.
- **Seed is deterministic** (`random.Random(42)`, fixed test dates) so the demo looks the same every run. Marks are in half-mark steps out of 10 per topic.
- **Seeded topics come from an NCERT "Curiosity" (2024) Class 6 Science chapter list** written from memory. Topic names inside chapters are our own breakdown. Worth a quick check against the book your school uses.
- **Passwords:** all demo accounts share `demo1234` and are shown on the login page. Turn off with `DEMO_MODE=false`.

## Frontend

- **Next.js 16 (App Router) + Tailwind 4 + Recharts.** This Next version differs from older ones, so we read the bundled docs in `node_modules/next/dist/docs` before using an API.
- **Auth state lives in a React context** with the token in `localStorage` (guarded, because storage can throw). A 401 anywhere signs the user out.
- **No UI library.** A few small components (`components/ui.tsx`) cover buttons, cards, spinners, empty and error states.

## Local environment

- **Docker ports:** the backend publishes on **8010**, not 8000, because another project on this machine already uses 8000. Both ports are set in `.env`.
- **OneDrive:** the project sits in a OneDrive-synced folder. Python's virtualenv lives in `~/.venvs/lms`, and the frontend's `node_modules` and `.next` are junctions to `~/.lms-cache/frontend`, so OneDrive never syncs thousands of tiny files. Docker volumes hold Postgres data and uploads.
- **Turbopack refuses a `node_modules` junction** that points outside the project, so local commands use webpack (`npm run dev:local`, `npm run build:local`). Docker builds use a real `node_modules` and the default Turbopack build.

## Free-tier limits that shape the design (measured)

- **Every Groq model on this key is capped at 8,000 tokens per minute** (and 1,000 requests). Each model has its own bucket. This is why long documents are never sent whole, why OCR is sequential, and why the AI layer waits out `429` responses using the `Retry-After` header (up to 30 s).
- **A handwriting page costs about 2,100 tokens regardless of image size**, so about three pages a minute. Uploads are capped at 5 pages, and images are shrunk to 1400 px only to keep uploads small.
- **Interview turns and practice quizzes use the fast model (`gpt-oss-20b`)** so they don't compete with question generation for the same bucket.
- Blocking AI calls run in a thread pool, so one person's OCR never freezes the server for everyone else.

## Handwriting OCR: what we measured, honestly

- On the synthetic samples the vision model scored **100% word accuracy** (neat and messy). That is optimistic: the pages are rendered from fonts. See `sample_data/README.md`. Real handwriting numbers need real photos.
- **The model does not reliably flag its own mistakes.** On a heavily blurred page it wrote "moves up" for "rises up" and marked nothing as uncertain. On clean pages it flags nothing because it reads everything correctly. So the yellow "words to check" highlighting works (tested in a browser) but will rarely fire. The review screen is the real safety net, and its wording says so.
- Options if reliable flagging is needed: (1) read each page twice with different preprocessing and highlight words where the readings disagree (doubles token cost, so about 1.5 pages a minute on this tier), or (2) a cloud OCR service that returns true per-word confidence (another vendor and key). Not done: it isn't worth the cost or complexity for the POC unless real-handwriting tests show a need.
- Vision calls use temperature 0 so the same page gives the same text.

## Notes Library

- **One `notes` table for everything** (handwritten, typed, uploaded). OCR results start as a *draft* so the review screen can show the original pages; they enter the library only when the user saves.
- **Access rules live in one function** (`services/notes_access.py`). A note you may not see is reported as *not found* (404), never *forbidden*, so guessing ids reveals nothing. A test proves the privacy tests fail when the rule is deliberately broken.
- **Students' practice quizzes are ephemeral** and never touch the Question Bank. The teacher-reviewed generator is a separate feature.
- Page images are fetched with the login token and shown from a blob URL, because a plain `<img>` can't send an Authorization header.

## Question Bank

- **Up to 3 versions per note** (balanced, application/thinking, recall/understanding). Each version reads a different third of a long note and is shown the earlier questions to avoid, so versions differ in substance and not only in wording.
- **Every question is validated in code** before a teacher sees it: type-specific shape (4 distinct MCQ options, a real blank, True/False answer), and the answer must appear in the note text. Ungrounded questions are dropped.
- **Honest shortfall:** if a note cannot support N good questions, the teacher sees the smaller number and a plain explanation. There is no filler.
- **Duplicate detection is plain word overlap, no embeddings.** Two measures must agree (share of the smaller question's words found in the other, and Jaccard) and at least 3 meaningful words must be shared. Tuned on real regenerations: earlier settings flagged distinct short questions ("Copper is strongly attracted..." vs "Which of these materials is attracted...") and are pinned by regression tests. It will miss a truly different wording of the same fact.
- **Known limit:** version 3 (recall) can run out of distinct facts on a short note and returns fewer questions with a message.
- **Speed:** 10 questions from a 10-page note take about 3 to 6 seconds (target was under 60).
- **Only accepted questions reach the bank, papers and tests.** Editing is validated server-side (an edit that would break a question is refused).
- **PDF is the browser's Print / Save as PDF** with a print stylesheet that shows only the paper, so there is no PDF library to maintain. DOCX is generated on the server.
- **Assign as test** creates an assessment for one class; the student-facing test screens arrive with Block 6.

