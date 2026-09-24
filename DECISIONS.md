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
