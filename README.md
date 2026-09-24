# myClassBoard-LMS: AI Learning Assistant (POC)

A standalone proof of concept showing how AI can reduce manual work for teachers and give students and parents clearer insight. It has five modules, all driven by synthetic Class 6 CBSE Science data:

| # | Module | Who | What it does |
|---|---|---|---|
| 1 | Question Bank | Teacher | Upload notes, get grounded questions (up to 3 versions), review, export a paper |
| 2 | Handwriting OCR + Notes Library | Teacher, Student | Photo of handwritten notes becomes editable digital text |
| 3 | Assessment (lite) | Student | Take a test, get a topic-wise report and weak-topic suggestions |
| 4 | Parent Summary | Teacher, Parent | Plain-language performance summary, teacher-approved, numbers computed in code |
| 5 | Interview Bot | Student, Teacher | Adaptive 7-question oral or typed interview with a feedback report |

> **Status:** under active development. See [docs/PLAN.md](docs/PLAN.md) for the block-by-block plan and progress.

## Documentation

| Doc | Purpose |
|---|---|
| [docs/PLAN.md](docs/PLAN.md) | Execution plan, tasks, check-ins, cut list |
| [docs/SUGGESTIONS.md](docs/SUGGESTIONS.md) | Approach and reasoning behind the design |
| [docs/project_requirements.txt](docs/project_requirements.txt) | Original project brief |
| `DECISIONS.md` | Choices made along the way and why (added as we build) |
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

Then open:

- App: http://localhost:3000
- API docs (Swagger): http://localhost:8000/docs

Setup steps for each module are added here as the modules land.

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
