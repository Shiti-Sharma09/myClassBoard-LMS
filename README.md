# myClassBoard-LMS: AI Learning Assistant (POC)

A standalone proof of concept showing how AI can reduce manual work for teachers and give students and parents clearer insight. It has five modules, all driven by synthetic Class 6 CBSE Science data:

| # | Module | Who | What it does |
|---|---|---|---|
| 1 | Question Bank | Teacher | Upload notes, get grounded questions (up to 3 versions), review, export a paper |
| 2 | Handwriting OCR + Notes Library | Teacher, Student | Photo of handwritten notes becomes editable digital text |
| 3 | Assessment (lite) | Student | Take a test, get a topic-wise report and weak-topic suggestions |
| 4 | Parent Summary | Teacher, Parent | Plain-language performance summary, teacher-approved, numbers computed in code |
| 5 | Interview Bot | Student, Teacher | Adaptive 7-question oral or typed interview with a feedback report |

> **Status:** under active development. See [docs/PLAN.md](docs/PLAN.md) for the block-by-block plan, and the Progress table below.

## Documentation

| Doc | Purpose |
|---|---|
| [docs/PLAN.md](docs/PLAN.md) | Execution plan, tasks, check-ins, cut list |
| [docs/SUGGESTIONS.md](docs/SUGGESTIONS.md) | Approach and reasoning behind the design |
| [docs/project_requirements.txt](docs/project_requirements.txt) | Original project brief |
| [DECISIONS.md](DECISIONS.md) | Choices made along the way and why |
| `METRICS.md` | Measured results against the success metrics (added in the final block) |

## Tech stack

Next.js + Tailwind + Recharts · FastAPI (Python 3.12) · PostgreSQL · Docker Compose · Groq API (LLM and vision) · browser Web Speech API (voice)

## Prerequisites

- Docker Desktop (with Compose v2)
- A free [Groq](https://console.groq.com) API key
- Google Chrome (needed for the voice interview)
- Git, and the [GitHub CLI](https://cli.github.com) if you want to create PRs from the terminal

## Quick start

```bash
# 1. Clone
git clone https://github.com/<your-username>/myClassBoard-LMS.git
cd myClassBoard-LMS

# 2. Configure secrets (never commit .env)
cp .env.example .env
#    then open .env and set GROQ_API_KEY

# 3. Run everything
docker compose up --build
```

The first start builds the images (a few minutes) and seeds the demo school automatically. Then open:

- App: http://localhost:3000
- API docs (Swagger): http://localhost:8010/docs

Ports are set by `FRONTEND_PORT` and `BACKEND_PORT` in `.env`. If a port is already taken on your machine, change it there and re-run `docker compose up --build`.

To stop: `docker compose down`. To wipe the database and start fresh: `docker compose down -v`.

## Demo accounts

Every demo account uses the password `demo1234`. The login page has one-click buttons for these:

| Role | Email | Notes |
|---|---|---|
| Teacher | `teacher@demo.school` | Sees both classes |
| Admin | `admin@demo.school` | |
| Student | `aarav@demo.school` | Strong student |
| Student | `diya@demo.school` | Average student |
| Student | `rohan@demo.school` | Weak student |
| Parent | `parent.aarav@demo.school` | Also `parent.diya@…`, `parent.rohan@…` |

All 15 students follow the pattern `<firstname>@demo.school`, and their parents `parent.<firstname>@demo.school`. Personas: strong, average, weak, improving, declining, and "gap" (strong overall but weak in one chapter).

## Development

```bash
# Backend tests (fast, no Docker needed): use a virtualenv OUTSIDE any cloud-synced folder
python -m venv ~/.venvs/lms
~/.venvs/lms/bin/pip install -r backend/requirements.txt      # Windows: ~/.venvs/lms/Scripts/pip
cd backend && ~/.venvs/lms/bin/python -m pytest

# Live check that Groq works with your key (main, fast and vision models)
cd backend && ~/.venvs/lms/bin/python -m scripts.ai_check

# Frontend checks
cd frontend && npm install && npm run lint && npx tsc --noEmit && npm run build
```

**Working inside OneDrive or Dropbox?** Syncing `node_modules` is slow and can lock files. Keep the virtualenv outside the folder and link `frontend/node_modules` and `frontend/.next` to a folder outside it (a Windows junction: `New-Item -ItemType Junction`). Turbopack rejects such links, so use `npm run dev:local` and `npm run build:local` (webpack) for local work. Docker builds are unaffected. Details in [DECISIONS.md](DECISIONS.md).

## Progress

| Block | Status |
|---|---|
| 1. Foundation (auth, seed data, AI layer, app shell, Docker) | Done |
| 2. Sample content (typed notes, handwriting images, ground truth) | Done |
| 3. OCR + Notes Library | Next |
| 4. Question Bank | Planned |
| 5. Parent Summary | Planned |
| 6. Assessment (lite) | Planned |
| 7-8. Interview Bot (text, then voice) | Planned |
| 9. Admin, metrics, polish | Planned |

## Privacy and data

- All data in this POC is **synthetic**. No real student data is used.
- Text and images you submit are sent to **Groq** to generate questions, read handwriting, write summaries and run the interview. The interview's voice is converted to text by the **browser** (Chrome sends audio to Google for this); the app itself **never stores audio**, only transcripts.
- Student data is not used for model training by this project.
- API keys live only in `.env`, which is git-ignored.

## Git workflow

- `main` is always in a working state. Never commit to it directly (the initial scaffold is the only exception).
- One branch and one pull request per block of work, named `feat/<block>`, `fix/<topic>` or `docs/<topic>`.
- [Conventional Commits](https://www.conventionalcommits.org): `feat:`, `fix:`, `docs:`, `test:`, `chore:`, `refactor:`.
- Pull requests are **squash-merged**, so `main` reads as one clean commit per block.
- Secrets, `node_modules`, uploads and build output are covered by `.gitignore`.

### Publishing this repo for the first time (already done for this project)

```bash
git init -b main
git add . && git commit -m "chore: initial scaffold"
gh repo create myClassBoard-LMS --private --source . --remote origin --push
```

## License

Internal proof of concept. No license granted.
