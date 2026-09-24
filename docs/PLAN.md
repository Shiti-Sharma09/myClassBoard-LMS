# PLAN: Executing the AI Learning Assistant POC

Follows the approach in `SUGGESTIONS.md`. The first half is tables you can scan in a minute. The second half explains each block in detail.

**Legend:** 🟦 = Claude builds · 🟩 = Shiti provides or reviews · ✅ = exit check (block is not "done" until this passes)

---

# PART 1: THE PLAN IN TABLES

## 1.1 Plan at a Glance


| # | Block                  | Day   | Est. time | What you get                                                                | Depends on  | Exit check                                                               |
| - | ---------------------- | ----- | --------- | --------------------------------------------------------------------------- | ----------- | ------------------------------------------------------------------------ |
| 0 | Prep                   | Day 1 | 0.5 h     | Groq key set, models confirmed, chapter list approved                       | Shiti's key | ✅ A test call to Groq returns text and reads an image                   |
| 1 | Foundation             | Day 1 | 2.5 h     | Running app skeleton, login for 4 roles, seeded database, AI layer          | 0           | ✅`docker compose up` then login as each role                            |
| 2 | Sample content         | Day 1 | 1 h       | Notes PDFs/DOCX, handwriting images, ground-truth text                      | 1           | ✅ Files open and look realistic                                         |
| 3 | OCR + Notes Library    | Day 1 | 2.5 h     | Upload photo, review screen, saved notes, sharing, DOCX download            | 1, 2        | ✅ Photo becomes a saved note; student cannot see another student's note |
| 4 | Question Bank          | Day 1 | 3.5 h     | Topic map, generation, 3 versions, review, bank, DOCX paper, assign as test | 1, 2, 3     | ✅ 10 questions from a 10-page note in under 60 s                        |
| 5 | Parent Summary         | Day 2 | 2 h       | Metrics, narrated draft, number check, charts, approve flow                 | 1           | ✅ Parent sees approved summary; every number matches the data           |
| 6 | Assessment-lite        | Day 2 | 2 h       | Student takes test, scoring, topic report, "practice this topic"            | 4           | ✅ Weak topics on the report match the answers given                     |
| 7 | Interview Bot (text)   | Day 2 | 2.5 h     | Adaptive interview, end report, transcripts, teacher filters                | 1, 3        | ✅ Strong and weak personas get visibly different question paths         |
| 8 | Interview Bot (voice)  | Day 2 | 1.5 h     | Hands-free voice on top of text bot, consent notice, controls               | 7           | ✅ Full 7-question spoken interview in Chrome                            |
| 9 | Admin, metrics, polish | Day 2 | 2 h       | Admin panel,`METRICS.md`, tests, README, DECISIONS, demo script             | all         | ✅ A fresh person can follow README and run the demo                     |

**Total:** about 20 working hours across 2 days. This is tight, so Section 1.5 lists what we cut if we run late.

## 1.2 Task Breakdown by Block


| Block | Task                                                                                            | Output (files or behaviour)                | Owner   |
| ----- | ----------------------------------------------------------------------------------------------- | ------------------------------------------ | ------- |
| **0** | Create`.env` with `GROQ_API_KEY`                                                                | `.env` (never committed or pasted in chat) | 🟩      |
| 0     | Check which Groq text and vision models are free, support JSON, and accept images               | Model names for`.env.example`              | 🟦      |
| 0     | Review seeded Class 6 Science chapter list                                                      | Approved list                              | 🟩      |
| **1** | Repo skeleton and Docker Compose (db, backend, frontend)                                        | `docker-compose.yml`, Dockerfiles          | 🟦      |
| 1     | DB models and`create_all()`                                                                     | `models.py`                                | 🟦      |
| 1     | Auth (JWT,`require_role`), demo login buttons                                                   | `auth.py`, login page                      | 🟦      |
| 1     | AI layer:`LLMClient`, `VisionClient`, retry, timeout, JSON validation, logging                  | `ai/` package                              | 🟦      |
| 1     | Prompt loader for versioned`.md` templates                                                      | `prompts/` folder                          | 🟦      |
| 1     | Seed script: school, 2 classes, 15 students, teacher, parents, personas, chapters, 5 to 6 tests | `seed/seed.py`                             | 🟦      |
| 1     | App shell: nav per role, shared UI components (Spinner, EmptyState, ErrorBanner)                | `frontend/components`                      | 🟦      |
| **2** | Write 4 to 5 Class 6 Science notes (one about 10 pages)                                         | `sample_data/notes/*.pdf, .docx`           | 🟦      |
| 2     | Generate handwriting-style images, neat and messy, with ground-truth text                       | `sample_data/handwritten/*`                | 🟦      |
| 2     | Photograph 2 to 3 real handwritten pages (optional)                                             | Extra messy samples                        | 🟩      |
| **3** | Image pre-processing (Pillow)                                                                   | `services/ocr_preprocess.py`               | 🟦      |
| 3     | Vision OCR call with uncertain-word markers, multi-page                                         | `services/ocr.py`, prompt                  | 🟦      |
| 3     | Review screen (image beside text, highlights, edit, save)                                       | `notes/review` page                        | 🟦      |
| 3     | Notes Library: list, search, edit, share, DOCX download, typed notes                            | `routers/notes.py`, pages                  | 🟦      |
| 3     | Access rules and their tests                                                                    | `tests/test_notes_access.py`               | 🟦      |
| **4** | Text extraction (PDF, DOCX, TXT), topic chunking                                                | `services/extract.py`                      | 🟦      |
| 4     | Topic map generation (editable)                                                                 | prompt + endpoint                          | 🟦      |
| 4     | Question generation with count top-up and thin-note banner                                      | `services/questions.py`                    | 🟦      |
| 4     | 3 versions with emphasis, duplicate check                                                       | prompt variants,`services/dedupe.py`       | 🟦      |
| 4     | Review UI (edit, accept, discard), Question Bank with filters                                   | pages                                      | 🟦      |
| 4     | Paper builder (sections, marks), DOCX export, print-to-PDF page                                 | `services/export_docx.py`                  | 🟦      |
| 4     | "Assign as test" for a class                                                                    | `assessments` table + endpoint             | 🟦      |
| **5** | Metrics computation (averages, trend, weak/strong topics)                                       | `services/metrics.py` + tests              | 🟦      |
| 5     | Narration prompt, JSON schema, number verifier                                                  | `services/summary.py` + tests              | 🟦      |
| 5     | Teacher review page (generate, edit, approve, approve all)                                      | pages                                      | 🟦      |
| 5     | Parent view with bar chart, trend line, weak-topic highlight                                    | pages                                      | 🟦      |
| **6** | Student test-taking page                                                                        | page                                       | 🟦      |
| 6     | Scoring: code for MCQ, true/false, fill-in; LLM for short and long                              | `services/scoring.py`                      | 🟦      |
| 6     | Report: topic bar chart, top 3 priorities, "Practice this topic"                                | page                                       | 🟦      |
| **7** | Interview state model and transition rules                                                      | `services/interview_state.py` + tests      | 🟦      |
| 7     | Turn endpoint (rate answer, pick next move, next question)                                      | `routers/interviews.py`, prompt            | 🟦      |
| 7     | End report (band in code, text from LLM)                                                        | prompt + service                           | 🟦      |
| 7     | Interview UI (text), transcript pages, teacher filters                                          | pages                                      | 🟦      |
| **8** | `speech.ts` wrapper (recognition, synthesis, `stopSpeaking`)                                    | frontend lib                               | 🟦      |
| 8     | Consent notice, mic controls, error and low-confidence handling                                 | UI                                         | 🟦      |
| 8     | Test on the demo laptop with your real mic                                                      | Latency and accuracy notes                 | 🟩      |
| **9** | Admin panel (reset demo data, weak-topic threshold)                                             | page + endpoints                           | 🟦      |
| 9     | Eval script (WER for OCR, accept rate, timing) writing`METRICS.md`                              | `scripts/eval/`                            | 🟦      |
| 9     | README,`DECISIONS.md`, demo script, `.env.example`                                              | docs                                       | 🟦      |
| 9     | Full dry run as teacher, student, parent, admin                                                 | Bug list, fixes                            | 🟩 + 🟦 |

## 1.3 Check-ins (where I stop and wait for you)


| After block | What you do                                                                   | Time needed |
| ----------- | ----------------------------------------------------------------------------- | ----------- |
| 1           | Log in as each role and confirm the look and feel                             | 10 min      |
| 3           | Upload a real photo of handwriting and check the review screen                | 10 min      |
| 4           | Generate questions from a real note, edit and accept some, download the paper | 15 min      |
| 5           | Read one parent summary and compare it with the seeded marks                  | 10 min      |
| 7           | Run one interview as the strong persona, one as the weak, compare             | 15 min      |
| 8           | Speak a full interview in Chrome                                              | 10 min      |
| 9           | Final dry run using the demo script                                           | 30 min      |

## 1.4 Success Metrics and How Each Is Measured


| Metric (from the brief)           | Target                                         | How we measure                                                            | Where it is reported |
| --------------------------------- | ---------------------------------------------- | ------------------------------------------------------------------------- | -------------------- |
| Questions usable                  | 80% or more                                    | Accept ÷ (accept + discard) from the review screen                       | `METRICS.md`         |
| Generation speed                  | 10 questions from a 10-page note in under 60 s | Timer logged around the generation call                                   | Logs,`METRICS.md`    |
| OCR word accuracy                 | 90% or more on neat writing                    | `jiwer` WER on samples with ground truth. Neat and messy shown separately | `METRICS.md`         |
| Parent summary figures            | 100% match                                     | Number verifier runs on every summary, failures counted                   | Tests,`METRICS.md`   |
| Weak topics correct               | 4 of 5 test cases agree with the teacher       | 5 seeded students, you judge the highlighted topics                       | `METRICS.md`         |
| Interview adapts                  | Different question path for strong and weak    | Two scripted persona runs, compared side by side                          | `METRICS.md`         |
| Interview on topic                | 95% or more                                    | Scripted off-topic prompts, count redirects                               | `METRICS.md`         |
| Voice response time               | About 3 s or less                              | Timestamp from end of speech to start of bot audio, logged                | Logs                 |
| Students cannot see others' notes | 100%                                           | Automated access test                                                     | pytest               |

## 1.5 Cut List and Risk Triggers


| If this happens                                                | Then do this                                                                                                                 |
| -------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------- |
| Day 1 ends and block 4 is not finished                         | Drop the print-to-PDF page and the paper section editing (keep flat DOCX with editable marks), then start Day 2 with block 5 |
| Groq vision reads handwriting poorly (under about 80% on neat) | Add a second free provider for OCR only (about 30 lines, thanks to the AI layer). Keep the review screen as the safety net   |
| Groq rate limit (429) keeps appearing                          | Switch the interview to the smaller fast model, shorten prompts, wait for reset, do the final dry run last                   |
| Voice is flaky by end of block 8                               | Keep the voice loop basic (speak question, listen, transcribe), drop replay and skip controls, keep text mode prominent      |
| Block 9 is squeezed                                            | Keep tests, README and the demo script. Drop admin beyond "Reset demo data" and the trend chart in Assessment                |
| Still behind                                                   | Radar chart and difficulty split were never in scope, so cut nothing there. Next to go is Assessment-lite polish             |

**Never cut:** the number verifier, the notes access test, loading and error states, and the text fallback in the interview.

## 1.6 Inputs Needed From You


| When               | What                                                         | Why                                |
| ------------------ | ------------------------------------------------------------ | ---------------------------------- |
| Before block 0     | Groq API key in`.env`                                        | Every AI feature needs it          |
| Before block 0     | Confirm "7 questions or 20 minutes, whichever comes first"   | Interview stop rule                |
| Before block 1     | Which NCERT Class 6 Science book (2024 "Curiosity" or older) | Chapter list for the dropdown      |
| Block 2 (optional) | 2 to 3 phone photos of your real handwriting                 | Honest messy-handwriting accuracy  |
| Block 9            | You act as teacher reviewer for the metrics                  | Quality numbers need a human judge |

---


# PART 2: DETAILED EXPLANATION

## 2.1 How the Work Is Ordered, and Why

The order follows what feeds what, not the order of the original brief.

1. **Foundation first**, because everything needs login, the database and the AI layer.
2. **Sample content second**, because OCR, questions and the interview all need real-looking notes to test against. Building on real content early exposes prompt problems immediately.
3. **OCR and Notes Library before Question Bank**, because a note is the object every other module uses. Once the library exists, questions, practice quizzes and interviews all just pick a note.
4. **Question Bank before Assessment**, since tests are built from accepted questions.
5. **Parent Summary is independent** (it uses seeded marks), so it can go anywhere. Day 2 morning is a good spot because it is mostly deterministic code and a good confidence boost after Day 1.
6. **Interview text before voice.** The brief's build order says the same: voice is just a layer on the working text engine. If the text bot is wrong, voice makes it harder to debug.
7. **Polish last but not squeezed.** Block 9 has real time, because a demo fails on the small things: an empty state, a spinner that never ends, a rate-limit error shown as a stack trace.

## 2.2 Block 0: Prep (30 minutes)

**Goal:** remove surprises before writing code.

- You put your Groq key in a `.env` file. I will create `.env.example` with the variable names only (`GROQ_API_KEY`, `LLM_MODEL_MAIN`, `LLM_MODEL_FAST`, `VISION_MODEL`).
- I run a tiny script that calls Groq once with text and once with an image. This tells us which models are available, whether JSON output works on them, and roughly what the rate limits are. Groq changes its model list often, so I will not trust my memory.
- I show you the seeded chapter list for Class 6 Science so you can correct it.

**Exit:** both test calls succeed. If the vision call fails, we find out now, not on Day 1 afternoon.

## 2.3 Block 1: Foundation (2.5 hours)

**Folder layout** (inside `MyClassBoard/ai-learning-assistant/`):

```
ai-learning-assistant/
├── docker-compose.yml
├── .env.example
├── README.md · DECISIONS.md · METRICS.md
├── backend/
│   ├── app/
│   │   ├── main.py, config.py, db.py, models.py, auth.py
│   │   ├── routers/     (auth, notes, questions, assessments, summaries, interviews, admin)
│   │   ├── services/    (plain Python: metrics, dedupe, scoring, interview_state, extract, export_docx, ocr)
│   │   ├── ai/          (client interfaces, Groq implementation, retry, JSON validation)
│   │   └── prompts/     (versioned .md templates)
│   ├── seed/            (seed.py)
│   ├── scripts/eval/    (OCR WER, accept rate, timing)
│   └── tests/
├── frontend/            (Next.js, Tailwind, Recharts)
└── sample_data/         (notes, handwritten images, ground truth)
```

**Key pieces**

- **Database models.** `users` (role), `classes`, `students` (linked to a class and a parent), `chapters`, `topics`, `notes`, `question_sets`, `questions`, `assessments`, `attempts`, `attempt_answers`, `score_records` (seeded marks), `parent_summaries`, `interview_sessions`, `interview_turns`, `interview_reports`, `settings`. Slightly fewer than the brief's list, because "documents" and "notes" merge.
- **AI layer.** Small and boring: `LLMClient.complete_json(prompt_name, variables, schema)` renders the template, calls Groq, validates the JSON against a Pydantic schema, retries up to twice on bad output or a transient error, and logs model, tokens and time. `VisionClient.read_image(...)` works the same way. Nothing else in the codebase imports the Groq SDK.
- **Seed script.** Creates 1 teacher, 15 students in 2 classes, one parent per student (only a few parents need demo logins), 5 to 6 science tests over the chapters. Personas get deliberately shaped score histories: strong and steady, average, weak, improving, declining. The seed is deterministic (fixed random seed), so the demo looks the same every time.
- **Auth.** Login endpoint returns a JWT. A `require_role` dependency guards routes. The login page shows "Demo login" buttons.
- **UI shell.** A sidebar that changes by role, plus the reusable Spinner, EmptyState and ErrorBanner. Building these once now means every later page gets friendly states for free.

**Windows and OneDrive note:** `node_modules` and the Postgres data live in Docker volumes, so OneDrive is not asked to sync thousands of small files.

**Exit:** `docker compose up`, then log in as teacher, student, parent and admin, and each sees its own empty dashboard.

## 2.4 Block 2: Sample Content (1 hour)

- **Typed notes:** 4 to 5 Class 6 Science notes as PDF and DOCX (for example Components of Food, Separation of Substances, Magnets). One is deliberately about 10 pages so we can prove the "under 60 seconds" target. One is deliberately thin, to test the "not enough content" banner.
- **Handwriting-style images:** rendered with free handwriting fonts, then degraded to look like phone photos (slight rotation, uneven lighting, noise, blur). Two sets: **neat** and **messy**. Every image has a typed ground-truth text file for accuracy measurement.
- **Honest caveat:** font-based handwriting is easier than real handwriting. That is why I keep asking for 2 or 3 real photos: they make the messy-handwriting number believable.

**Exit:** files exist and look plausible when you open them.

## 2.5 Block 3: OCR and Notes Library (2.5 hours)

**Flow:** upload page → pre-process → vision model → review screen → save to library.

- **Pre-processing (Pillow):** apply the EXIF rotation, resize to a sensible width, convert to grayscale, auto-contrast. OpenCV deskew is added only if the messy samples need it. Over-processing can lower accuracy, so we test before adding steps.
- **Vision prompt:** asks the model to transcribe exactly, keep headings and bullets, and wrap any word it is unsure of in `[?…?]`. Multiple pages are read one request per page and joined.
- **Review screen:** original image on the left, editable text on the right, uncertain words highlighted. A note about limits is shown in the UI: English handwriting on ruled or plain paper, diagrams are kept as images and not interpreted.
- **Notes Library:** title, subject, chapter, topic, date, image, text. Search by keyword, edit, download as DOCX. Typed or uploaded notes go into the same library.
- **Role actions:** a teacher gets "Generate questions" and "Share with class". A student gets "Practice quiz" (5 questions with instant feedback, saved only for that student).
- **Access rules (backend enforced):** a query for notes always filters by `owner = me OR shared_with = my class`. A pytest test creates two students and proves one cannot fetch the other's note, even by guessing the URL.

**Exit:** a photo goes through the whole path, and the access test passes.

## 2.6 Block 4: Question Bank (3.5 hours)

This is the longest block because it is the core of the pitch.

1. **Extraction and chunking.** PyMuPDF for PDF, python-docx for DOCX, plain read for TXT. The text is split into topic chunks and stored.
2. **Topic map.** One LLM call proposes topics for the chosen chapter. The teacher can rename, merge or delete topics.
3. **Generation.** The form collects count, types, difficulty and version. The prompt includes only the relevant chunks, the rules ("use only this text, no outside facts"), and the JSON schema. Output includes question, options, answer, explanation, type, difficulty, topic and Bloom level.
4. **Count guarantee.** Code counts valid questions. If short, it makes one top-up call for the missing number. If the note is genuinely too thin, we keep what is good and show: "This note supports 7 good questions (you asked for 10)."
5. **Versions.** Version 1 is balanced, version 2 emphasises application and reasoning, version 3 emphasises recall plus topics students did poorly on. It is the same prompt with a different emphasis paragraph, and the earlier questions are passed in. A word-overlap similarity check rejects near-duplicates and asks for replacements.
6. **Review and bank.** Each question can be edited, accepted or discarded. Accepted ones land in the bank, organised Subject → Chapter → Topic with counts, and filters for type, difficulty and Bloom level. Accept and discard clicks are recorded for the usable-rate metric.
7. **Paper.** The teacher selects questions, sees them grouped into sections by type, edits marks and the title, and downloads a DOCX with an answer key. A separate print-styled page lets them "Save as PDF" from the browser.
8. **Assign as test.** Turns a selection into an assessment for a class, ready for block 6.

**Exit:** timing on the 10-page note is under 60 seconds, a paper downloads, and the thin note shows the banner.

## 2.7 Block 5: Parent Summary (2 hours)

- **Metrics first (no AI):** a plain function takes a student's score records and returns subject and topic averages, the trend across recent tests (improving, steady, declining), the strongest and weakest topics, and weak flags using the threshold (default 60%, class-level overrides from admin). Unit tests cover normal, edge and empty cases.
- **Narration:** the prompt gets the computed JSON and is told to restate, not calculate. The output schema has fixed fields: overall paragraph, strengths, areas to work on, trend sentence, and 2 to 3 home tips. The tone rule is "encouraging, plain, non-alarming, no jargon".
- **Number verifier:** extracts every number from the narrative and checks it appears in the input facts (allowing simple formatting like "72%" vs "72"). If any number is not found, the output is rejected and regenerated once. Failures are counted for `METRICS.md`.
- **Teacher review:** "Generate drafts for class", per-student editing, Approve and Approve all, Regenerate. Only approved summaries are visible to the parent.
- **Parent page:** the approved narrative plus three charts built from the computed data: subject-wise bars, a trend line and highlighted weak topics.

**Exit:** compare one summary against the seed data and see that every figure matches.

## 2.8 Block 6: Assessment-lite (2 hours)

- **Test page:** the student sees tests assigned to their class, answers questions and submits.
- **Scoring:** code scores MCQ, true/false and fill-in (case-insensitive match with a little trimming). For short and long answers the LLM compares the answer to the key and returns 0, half or full marks plus a one-line reason.
- **Report:** a plain function rolls scores up by topic. The page shows a topic bar chart with the weakest highlighted, and a top 3 priority list.
- **Loop back:** each weak topic has "Practice this topic", which opens question generation for that topic only (student practice quiz), and a link to the relevant note.

**Exit:** the weak topics on the report match the questions answered wrongly.

## 2.9 Block 7: Interview Bot, Text (2.5 hours)

**State kept in the database** (not only in the prompt): current difficulty, list of concepts from the note, per-concept ratings, questions asked so far, start time.

**One turn:**

1. The student's answer arrives at `POST /interviews/{id}/turn`.
2. The LLM returns JSON: rating of the last answer (0 to 2), the concept it touched, the next move (probe, follow-up on a gap, new concept), and the next question. Replies stay short so they sound natural when spoken.
3. Code applies the rules: two strong answers in a row raise difficulty, two weak ones lower it, concepts must come from the note, and the session stops at 7 questions or 20 minutes.
4. Off-topic answers get a polite redirect. No correct answers are revealed.

**End of interview:** the band (Needs support, Developing, Proficient, Excellent) is computed in code from ratings. The LLM writes concept-wise strengths and gaps, quotes from the student's own good and weak answers, and topics to revise. The report is checked against the transcript (only topics that were actually asked can appear).

**Views:** the student sees their own transcripts and reports. The teacher sees all students in the class, filterable by student, topic and date, and can not delete anything. Parents do not see interviews.

**Exit:** run the strong and weak personas on the same note and see different question paths.

## 2.10 Block 8: Interview Bot, Voice (1.5 hours)

- **`speech.ts`:** the only file that knows about browser speech. It exposes `listen()`, `speak(text)` and `stopSpeaking()`. Later switching to a server provider means editing just this file, and barge-in later means calling `stopSpeaking()` when speech is detected.
- **Turn-taking:** bot speaks → mic opens only after it finishes (so it never hears itself) → Chrome detects end of speech → transcript is shown → sent to the same `/turn` endpoint → repeat.
- **Low confidence:** if the browser reports low confidence, the bot says "I heard '…', is that right?" instead of guessing.
- **Controls:** mic on/off, replay last question, skip, switch to text at any time, end session.
- **Errors:** mic denied, no speech detected, unsupported browser → friendly message and automatic fallback to text.
- **Consent:** a short notice before the first voice session; only text transcripts are stored, never audio.
- **Latency:** Groq is fast, and replies are short, so the 3-second target is realistic even without streaming. The time from end of speech to start of bot speech is logged every turn.

**Exit:** you speak a complete 7-question interview hands-free on the demo laptop.

## 2.11 Block 9: Admin, Metrics and Polish (2 hours)

- **Admin panel:** "Reset demo data" (drop, recreate, reseed), and the weak-topic threshold setting.
- **Eval script → `METRICS.md`:** computes OCR word error rate (neat and messy separately), generation time, accept rate, number-verifier failures and interview-adaptation comparisons, and writes a one-page results file for the pitch.
- **Tests:** about five small pytest files for metrics, number verification, duplicate check, schema validation, interview transitions and notes access, plus a smoke script that hits each flow.
- **Docs:** `README.md` (setup, env vars, seed data, demo walkthrough, and what data goes to which provider, with a statement that student data is not used for model training), `DECISIONS.md` (every choice and why, including speech provider), and a **demo script**: a click-by-click path as teacher, student, parent and admin.
- **Final dry run:** we go through the demo script end to end, once as if in front of the client. Results are stored in the database, so the demo does not depend on a fresh AI call succeeding for everything.

## 2.12 Working Rhythm


| Step             | What happens                                                                           |
| ---------------- | -------------------------------------------------------------------------------------- |
| Build            | I write the block, run it, and test what can be tested automatically                   |
| Report           | I summarise what works, what does not, and anything I decided (added to`DECISIONS.md`) |
| Check-in         | You click through the flow from Section 1.3 and tell me what feels off                 |
| Fix and continue | I adjust, then move to the next block                                                  |

**Ground rules I will keep:** no secrets in code or chat, prompts always in template files, model names always from `.env`, every AI output validated, every AI output that reaches a parent or the Question Bank passes through a teacher first, and nothing built that is not in this plan without asking you.

---

**Next step:** send me your Groq API key setup (in `.env`, not in chat) and the four small confirmations in Section 1.6, and I will start Block 0.
