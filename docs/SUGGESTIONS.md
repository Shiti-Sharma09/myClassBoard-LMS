# SUGGESTIONS: How I Recommend We Build This POC

Written after reading `project_requirements.txt`, `AI_Study_Companion_Edtech_POC.docx` and your answers in `question_for_shiti.txt`.

The rule I am following: **build the smallest thing that makes all 5 modules work end to end in a live demo.** Nothing extra.

---

## 1. The Short Version

1. **Five modules, one small app.** Question Bank, Handwriting OCR, Assessment (lightweight), Parent Summary, Interview Bot (text and voice).
2. **One backend (FastAPI), one frontend (Next.js), one database (Postgres), all started with `docker compose up`.** No Redis, no Celery, no vector database, no microservices.
3. **Groq for all AI** (text, vision, and optionally speech), because it is free. Model names live in `.env`, so we can switch provider later.
4. **Voice runs in the browser** (Chrome's built-in speech recognition and speech synthesis). It is free, needs no keys and is fast. The backend never touches audio.
5. **Code does the maths, the AI does the words.** Scores, averages, weak topics, difficulty changes and interview scoring are all computed in normal code. The LLM only writes questions, narrates facts, reads handwriting and asks the next question.
6. **Every AI answer is checked** against a Pydantic schema before we use it. If it is invalid, retry once or twice, then show a friendly error.
7. **Two days means being strict about scope.** Section 9 has a day-by-day plan and a cut list for when we run late.
8. **Before we start, I need your Groq API key** and a quick check of which Groq models are currently free (Section 8).

---

## 2. What We Are Building (Locked From Your Answers)


| Area          | Decision                                                                                            |
| ------------- | --------------------------------------------------------------------------------------------------- |
| Modules       | All 5: Question Bank, OCR + Notes Library, Assessment-lite, Parent Summary, Interview Bot           |
| Curriculum    | CBSE, Class 6, Science only                                                                         |
| Data          | 1 school, 2 classes, 15 students, 5 to 6 science tests, with strong / average / weak personas       |
| AI provider   | Groq free tier, no budget, no cost dashboard (logs and README only)                                 |
| Voice         | English only, free option, no push-to-talk, hands-free                                              |
| Question sets | Max 3 versions per note (balanced, application-focused, recall + missed topics)                     |
| Exports       | Question paper as DOCX (PDF via print, see 4.1). Notes download as DOCX                             |
| Parent        | 1 parent = 1 child. No rank bands. English only                                                     |
| Teacher       | Cannot delete transcripts. Can filter interviews by student, topic and date                         |
| Admin         | Small panel: reset demo data, weak-topic threshold                                                  |
| Interview     | 7 questions or 20 minutes, whichever comes first. Grounded on a note. Never reveals correct answers |
| Deadline      | 2 days                                                                                              |

---

## 3. Architecture (Kept Deliberately Boring)

```
 Browser (Chrome)                      Backend (FastAPI)                 External
 ┌──────────────────────┐   REST      ┌──────────────────────────┐
 │ Next.js + Tailwind   │ ──────────► │ routers: auth, notes,    │
 │ Recharts             │ ◄────────── │ questions, assessments,  │      ┌────────┐
 │                      │   JSON      │ summaries, interviews,   │ ───► │  Groq  │
 │ Web Speech API       │             │ admin                    │      │  LLM   │
 │ (mic in, voice out)  │             │                          │      │ Vision │
 └──────────────────────┘             │ services (plain Python): │      └────────┘
                                      │ metrics, dedupe,         │
                                      │ interview state, scoring │
                                      │                          │
                                      │ ai/ (the ONE AI layer)   │
                                      │ prompts/*.md (versioned) │
                                      └────────────┬─────────────┘
                                                   │
                                            Postgres (Docker)
                                            + uploads/ folder
```

**Why this shape**

- **A single `ai/` module** is the only code that talks to Groq. It handles retries, timeouts, JSON validation and logging of tokens and time. Every module calls it. That gives us a swappable provider without building a plugin system: one small interface class, one implementation.
- **Prompts are `.md` files** (for example `prompts/question_gen.v1.md`). The brief asks for this, and it also makes prompts easy to tweak without touching Python.
- **No background job queue.** Groq is fast, so generation is a normal request with a loading spinner. Queues add setup time and failure modes we do not need for a demo.
- **No WebSockets.** Since the browser does speech-to-text and text-to-speech, the interview is just `POST /interviews/{id}/turn` with text. Voice is an interface layer on top of the same endpoint, exactly as the brief describes.

---

## 4. Key Decisions and Why

### 4.1 Exports

- **Question paper to DOCX** with `python-docx`. Marks and sections are editable in the app before export (you asked for this in D2). Sections are simply the question types (Section A: MCQ, and so on), with marks per question editable inline.
- **PDF via a "Print / Save as PDF" button** on a clean, print-styled page. This costs almost nothing. Generating real PDFs server-side inside Docker means extra libraries, and converting DOCX to PDF needs LibreOffice, which is heavy. I recommend the print route.
- Notes download as DOCX only, as you asked.

### 4.2 CBSE chapter tags (D4)

Low effort, so yes. We seed the Class 6 Science chapter list into a `chapters` table. The teacher picks a chapter from a dropdown at upload, and the AI proposes **topics inside that chapter** (teacher can edit). This gives the Subject → Chapter → Topic tree with no complicated syllabus mapping.

> One thing to check: NCERT changed the Class 6 Science book in 2024 ("Curiosity"). I will seed the current chapter list from memory, so please glance over it and tell me if your school uses the older book.

### 4.3 One `notes` table for everything

The two documents talk about "documents" and "notes". I suggest merging them. A **note** is any text source: an uploaded PDF/DOCX/TXT, an OCR result, or typed text. Each has an owner, an optional chapter/topic, and can be shared with a class. This lets the same object flow into question generation, practice quizzes and the interview bot, which is the whole loop from the .docx.

### 4.4 Two separate "score" worlds (as you decided in A3)

- `score_records`: seeded school test history, used **only** by the Parent Summary.
- `attempts` / `attempt_answers`: tests students take inside the app, used **only** by Assessment.

Keeping them apart avoids confusion and saves us building a bridge nobody asked for.

### 4.5 Auth

Email and password, a JWT in the header, and one small `require_role("teacher")` dependency on routes. No SSO, no refresh tokens, no password reset. The login page has "Demo login" buttons for each role.

### 4.6 Database setup

`create_all()` on startup plus a seed script. **No Alembic migrations.** It is a POC, and "Reset demo data" in the admin panel simply drops and reseeds.

### 4.7 Frontend

Next.js (App Router) + Tailwind + Recharts, plain `fetch` calls, no Redux or other state library. Clean, modern look with a small set of reusable components (Button, Card, Table, Modal, Spinner, EmptyState, ErrorBanner). Those last three are what stops the demo from "looking broken".

---

## 5. Module-by-Module Approach

### Module 1: Question Bank (teacher)

1. Upload PDF/DOCX/TXT (or pick an existing note). Extract text with PyMuPDF / python-docx.
2. Teacher picks chapter, class, question types, difficulty and count.
3. **One LLM call proposes topics** (a topic map). Teacher can edit them.
4. **One LLM call generates N questions** as JSON, each with type, options, answer, explanation, topic, difficulty and Bloom level.
5. **Code checks the result:** schema valid, count equals N, no duplicates. If short, do a top-up call for the missing ones. If the note is too thin, see D3 below.
6. **Versions (max 3):** the same generation prompt with a different "emphasis" line. Version 1 is balanced, version 2 is application and reasoning, version 3 is recall plus topics where students did badly in assessments. Previous questions are passed in, and a cheap similarity check (word overlap, no embeddings) rejects near-duplicates.
7. Teacher edits, accepts or discards each question. Accepted questions go to the bank, which has filters by topic, type, difficulty and Bloom level.
8. "Assign as test" turns a set of accepted questions into an assessment for a class (the .docx hand-off you chose in A5).

**Long documents:** for a 10 to 30 page note we do not need RAG or vector search. We split the text into topic chunks once, store them, and send only the relevant chunk(s) to the model. This keeps us inside Groq's free token limits and keeps questions grounded.

### Module 2: Handwriting OCR + Notes Library (teacher and student)

1. Upload JPG/PNG/PDF (multiple pages become one note).
2. **Light pre-processing** with Pillow: fix phone rotation (EXIF), resize to a sensible size, grayscale and auto-contrast. Add OpenCV deskew only if the test images need it. Heavy filtering can actually make a vision model worse, so we measure before adding more.
3. A Groq **vision model** reads each page and returns text with headings and bullets kept.
4. **Review screen:** original image on the left, editable text on the right. Words the model is unsure about are wrapped in markers (for example `[?word?]`) and highlighted. There is no numeric confidence score, as you asked.
5. Save to the Notes Library. Teachers can then send it to the question generator or share it with a class. Students can start a 5-question practice quiz from it (not saved to the Question Bank).
6. Typed notes can also be saved to the library (F6).
7. Access rules are enforced in the backend query, not just hidden in the UI: a student sees only their own notes plus notes shared with their class. This gets a proper test.

### Module 3: Assessment-lite (student takes a test, gets a report)

- Student sees tests assigned to their class and answers them in the browser.
- **MCQ, true/false and fill-in are scored by code.** Short and long answers are scored by the LLM against the answer key (0, half, or full marks plus a one-line reason). We skip the rubric editor and teacher override, since you chose the lightweight version.
- The **report** is computed in code: a bar chart by topic (weakest highlighted), a top 3 priority list, and a trend if the student attempts again.
- For each weak topic: a "Practice this topic" button, which calls Module 1 for a fresh set on that topic only. That is the "loop" the .docx sells.
- The radar chart and difficulty split are cheap in Recharts, so add them only if time remains.

### Module 4: Parent Summary

1. `seed_data.py` builds 15 students with 5 to 6 science tests each, following personas: strong, average, weak, improving, declining.
2. A plain Python function computes everything: subject and topic averages, trend, strongest and weakest topics, and the weak flag (below 60%, admin-configurable).
3. The LLM receives that computed JSON and writes the narrative (overall paragraph, strengths, areas to work on, 2 to 3 home tips). It is told never to calculate.
4. **Number check in code:** pull every number out of the narrative and confirm each one is in the facts we gave it. If not, retry once. This is what makes "100% figures match" true, not just hoped for.
5. Charts come from the computed data, never from the LLM.
6. The summary is saved as a **draft**. The teacher edits and approves it, and only then does the parent see it.

### Module 5: Interview Bot (text first, then voice)

**Rule: the conversation state lives in the backend, not in the prompt.** For each interview we store the current difficulty, the list of concepts from the chosen note, how each concept has gone so far, and how many questions have been asked.

Each turn works like this:

1. The student answer arrives (typed, or transcribed by the browser).
2. One LLM call returns JSON: a rating of the last answer (0 to 2), which concept it touched, and the next question. The LLM also decides whether to probe deeper, follow up on a gap, or move on.
3. **Code applies the rules:** two strong answers in a row raise the difficulty, two weak ones lower it, the bot stays on the note's concepts, and the interview stops at 7 questions or 20 minutes.
4. Off-topic messages are redirected. The system prompt handles this, and the "stay grounded in the note" rule keeps it tight.
5. At the end, **the score band is computed in code** from the per-answer ratings. The LLM only writes the readable feedback: strengths, gaps, examples from the student's own answers, and topics to revise. Since you said "no" to revealing correct answers, the report never includes model answers.

**Voice layer** (built only after text works):

- Speech to text: Chrome's `SpeechRecognition`. It detects end-of-speech itself, shows a live transcript, and reports a confidence value. Low confidence triggers "Did you say…?" instead of guessing.
- Text to speech: browser `speechSynthesis`, preferring an English-India voice if the machine has one.
- A single `speech.ts` file wraps both. That is our "provider interface" on the frontend. A stronger provider later means changing that one file.
- Controls: mic on/off, replay, skip, switch to text, end session. Mic denied, or no speech heard, drops to text with a friendly message.
- A short consent notice appears before the first voice session (see G2 below).

---

## 6. Your Questions, Answered in Plain Language

**C3: Which speech provider is best and free?**
Use the **browser's built-in speech** (Chrome). It is free, needs no key, is fast, and includes end-of-speech detection. The trade-offs are that it only works well in Chrome, the voice sounds a bit robotic, and Chrome sends the audio to Google for transcription. Groq also offers a Whisper speech-to-text model, and it has had a TTS model too, but they need audio recording, extra code and separate rate limits. I would only add that if the browser version disappoints. Also, browser recognition gives a confidence value, and Groq's Whisper does not give a simple one, so the browser version is better for our low-confidence handling.

**D3: What if the document is too thin for N questions?**
Best option: **generate as many good questions as the document supports and show a clear banner**, for example "This note only supports 7 good questions (you asked for 10). Add more content, or accept these 7." No invented filler and no extra button to build. The teacher can then still hit "regenerate" or upload more.

**D7: What are Bloom's level and "usable rate"?**

- **Bloom's level** is a label for the kind of thinking a question needs. It goes from *Remember* (recall a fact), *Understand*, *Apply*, and *Analyze* up to *Evaluate* and *Create*. It helps teachers balance a paper between easy recall and deeper thinking. I would show it as a small tag on each question and as a filter in the bank. That is enough.
- **Usable rate** is just accepted questions divided by (accepted + discarded). It is how we prove the "80% of questions are usable" metric. I would track it quietly, and show it only in the metrics report and logs, not on the teacher screens.

**E5: Best approval flow for parent summaries?**
Keep it simple:

1. Teacher clicks **"Generate drafts for class"**.
2. They review each student's draft (edit if needed) and click **Approve**. There is also an **Approve all** button for speed.
3. Each draft has a **Regenerate** button.
4. We skip the "stale summary" logic. The demo marks never change after seeding, so it would be code nobody sees.

**F2: Best way to measure OCR accuracy?**
A small script. We keep about 5 neat and 3 messy sample pages, each with a typed "ground truth". The script computes word error rate (with the `jiwer` library) and writes the result into `METRICS.md`. One honest caveat: **fake handwriting rendered from fonts is easier to read than real handwriting**, so numbers will look better than reality. The most credible fix takes about 10 minutes: **write 2 or 3 real pages by hand and photograph them with your phone**, and we add them to the messy set. I will report neat and messy numbers separately, as the brief demands.

**G2: Why is consent needed?**
The students are children, and a voice is personal data. Even though we do not store audio, in Chrome the audio is sent to Google to be transcribed. So before the first voice session we show one short notice ("Your voice is turned into text to run this interview. We only keep the text, not the recording."), and the student clicks OK. It is one small screen. It is cheap, and it is something a school client will look for. We skip the parent-consent database flag for the POC.

**G7: What does a "score band" mean?**
A band is a plain-language label for how the interview went, instead of a harsh number. I suggest four, computed by code from the answer ratings:

- **Needs support**, **Developing**, **Proficient**, **Excellent**

The report shows the band plus simple facts such as "5 of 7 answers were strong", and then the concept-wise strengths and gaps. It avoids a number that looks like an exact AI grade.

**G8: What is VAD and do we need it?**
VAD (voice activity detection) is how the app knows *when the student has finished speaking*, so it can move on without a "press to talk" button. Chrome's built-in speech recognition already does this, so **we do not need to add a VAD library**. It would only matter if we later switch to server-side transcription.

**G10: Can the bot filter out background noise, and not hear itself?**

- **Hearing itself:** we solve this by design. The mic only opens *after* the bot finishes speaking, so it can never transcribe its own voice.
- **Background noise:** browsers already apply noise suppression and echo cancellation to the mic. We cannot promise to separate one person's voice from another's with free tools. The practical advice is to **use a headset or a quiet room for the demo**, and rely on the "Did you say…?" confirmation for unclear speech.
- This also means no push-to-talk button, as you wanted.

**G4: "7 questions for 20 time limit"**
I read this as: stop at **7 questions or 20 minutes, whichever comes first.** I will not add "end early" logic beyond that, which keeps the interview predictable for a demo. Tell me if you meant something else.

**H3: Adult / self-learner accounts?**
Skip it. Every student belongs to a class in this POC. Coaching-institute learners are a possible later extension.

---

## 7. What We Are Deliberately NOT Building

- Redis, Celery, message queues, or a vector database
- Alembic migrations, multi-tenant schools, SSO, password reset
- WebSockets, server-side audio pipeline, real VAD, barge-in (we leave a `stopSpeaking()` hook, that is all, as you asked in G9)
- A cost or metrics dashboard in the app (logs and README only, as you said)
- Hindi or any other language, radar and difficulty charts (unless time remains), rank bands, teacher override of LLM grading
- Encryption at rest (we document it as future work; data is synthetic)
- Offline demo mode (you confirmed a stable connection)
- A generic "plugin" provider framework. One small interface and one Groq implementation is enough.

---

## 8. Risks I Want You to Know About


| Risk                                        | Why it matters                                                                                                                                                | What we do                                                                                                                                                                                                                                                 |
| ------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Groq free-tier limits**                   | Free plans have per-minute and per-day request and token caps. Heavy testing can use up a day's quota, and a 429 error in the middle of a demo would look bad | Retry with backoff. Use a small fast model for the interview and a larger one for question generation and OCR. Send only the relevant topic chunk, not whole documents.**Do a full dry run just before the demo**, since results are saved in the database |
| **OCR quality on Groq vision models**       | Their handwriting reading is decent but not top-tier, so 90% on neat writing is a real target, not a given. Messy handwriting will be lower                   | The review screen is the safety net. We measure honestly and report neat and messy separately. If accuracy disappoints, adding a second provider (for example Gemini's free tier) for OCR only is about 30 lines, because of the single AI layer           |
| **Model names change**                      | Groq retires and adds models often, so any name I type from memory could be out of date                                                                       | All model names live in`.env`. At the start I will check the Groq console for currently available, free models with JSON and image support                                                                                                                 |
| **Voice only works in Chrome**              | Firefox and Safari have weak or no speech recognition                                                                                                         | Demo in Chrome, keep text mode one click away                                                                                                                                                                                                              |
| **Voice needs internet and mic permission** | Chrome's recognition is online                                                                                                                                | You confirmed stable internet. We test mic permission early on the demo laptop                                                                                                                                                                             |
| **OneDrive + Docker + node_modules**        | Your project folder is inside OneDrive. Syncing thousands of`node_modules` files can slow builds and cause file-lock errors                                   | Keep`node_modules` and the DB data in Docker volumes, not the synced folder. Or pause OneDrive syncing while we work. I will set up the compose file this way                                                                                              |
| **2 days for 5 modules**                    | This is a very tight plan                                                                                                                                     | See the plan and cut list below                                                                                                                                                                                                                            |

---

## 9. Two-Day Plan

A short check-in after each block (your "stop after each phase" default). I build and test, you click through and tell me what feels wrong.

### Day 1: Foundation and Content


| Block | What                                                                                                                                                                               | Done when                                                                     |
| ----- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------- |
| 1     | Foundation: Docker Compose, DB models, auth + roles, demo accounts, seed script (school, 15 students, personas, chapters), AI layer, prompt loader, README skeleton,`.env.example` | `docker compose up` gives a working login for all 4 roles                     |
| 2     | Sample content: synthetic Class 6 Science notes (typed PDF/DOCX including one about 10 pages), handwriting-style images (neat and messy) plus ground truth text                    | Files exist in`sample_data/`                                                  |
| 3     | **OCR + Notes Library** (upload, pre-process, review screen, save, share, DOCX download, access rules)                                                                             | A photo becomes a saved note, and a student cannot see another student's note |
| 4     | **Question Bank** (topic map, generation, count top-up, 3 versions, dedupe, edit/accept/discard, bank filters, DOCX paper with editable marks/sections, assign as test)            | 10 questions from a 10-page note in under 60s, and a paper downloads          |

### Day 2: Insight, Interview and Polish


| Block | What                                                                                                                 | Done when                                                     |
| ----- | -------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------- |
| 5     | **Parent Summary** (metrics, narration, number check, charts, draft → approve → parent view)                       | Parent sees an approved summary, and every number matches     |
| 6     | **Assessment-lite** (student takes test, scoring, report, priority list, "practice this topic")                      | Report highlights the right weak topics                       |
| 7     | **Interview Bot, text** (state, adaptive rules, end report, transcript viewing, teacher filters)                     | Strong and weak personas get visibly different question paths |
| 8     | **Interview Bot, voice** (speech.ts, consent notice, controls, error handling)                                       | 7-question hands-free interview in Chrome                     |
| 9     | **Admin panel, eval script → `METRICS.md`, tests, README, `DECISIONS.md`, demo script, empty/loading/error states** | Someone else can follow the README and the demo, with no help |

### If we fall behind, cut in this order

1. Radar chart and difficulty split (never started)
2. Print-to-PDF polish (DOCX only)
3. Admin panel beyond "Reset demo data"
4. Voice polish (replay/skip controls), while keeping a working voice loop
5. Assessment-lite trend chart

**Never cut:** the number check in Parent Summary, the notes access-control test, the loading/error states, and the text fallback in the interview. Those are what keep the demo from failing in front of a client.

### Tests we will write (only the deterministic parts)

Metric computation, number verification, duplicate check, schema validation, interview state changes and notes access rules. That is about five small pytest files, plus one smoke script that walks each flow. No heavy UI test setup.

---

## 10. What I Need From You

1. **Groq API key** (put it in `.env`, never in chat or code). I will check which models are currently free and suitable.
2. **Confirm G4:** 7 questions or 20 minutes, whichever comes first.
3. **Which NCERT Class 6 Science book** your reference uses (new 2024 "Curiosity" or the older one)? A glance at the seeded chapter list is enough. is there a major difference use the new one
4. **Who plays the "teacher reviewer"** for the metrics (accept/discard rate, and "do these weak topics match your judgement" for 5 test students)? Is that you? yes
5. **Optionally:** 2 or 3 pages of real handwriting photographed on your phone, for an honest OCR test. you can extracte it form browser

When you say go, I start with Block 1 and confirm before moving on.
