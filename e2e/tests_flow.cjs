// End-to-end walk through Assessment: a student takes a test, sees a topic report, and practises a weak topic.
//
//   docker compose up -d --build        (from the repo root, with GROQ_API_KEY set: it makes real AI calls)
//   cd e2e && npm install && npx playwright install chromium && npm run tests
//
// Setup goes through the API (covered by questions_flow): upload a note, generate and accept questions, share
// the note with class 6-A and assign the questions as a test. Then the student side runs in the browser.
const { chromium } = require("playwright");
const fs = require("fs");
const path = require("path");

const APP = process.env.APP_URL || "http://localhost:3000";
const API = process.env.API_URL || "http://localhost:8010";
const SHOTS = process.env.SHOTS || path.join(__dirname, "shots");
fs.mkdirSync(SHOTS, { recursive: true });

const results = [];
const check = (name, ok, detail = "") => {
  results.push({ name, ok });
  console.log(`${ok ? "PASS" : "FAIL"}  ${name}${detail ? "  (" + detail + ")" : ""}`);
};

async function call(token, method, url, body) {
  const res = await fetch(`${API}${url}`, { method, headers: { Authorization: `Bearer ${token}`, ...(body && !(body instanceof FormData) ? { "Content-Type": "application/json" } : {}) }, body: body instanceof FormData ? body : body ? JSON.stringify(body) : undefined });
  if (!res.ok) throw new Error(`${method} ${url} -> ${res.status} ${await res.text()}`);
  return res.json();
}

async function setup() {
  const login = await fetch(`${API}/api/auth/login`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ email: "teacher@demo.school", password: "demo1234" }) });
  const token = (await login.json()).token;
  const chapters = await call(token, "GET", "/api/chapters");
  const classes = await call(token, "GET", "/api/classes");
  const classA = classes.find((c) => c.name === "6-A");
  const form = new FormData();
  form.append("file", new Blob([fs.readFileSync(path.join(__dirname, "..", "sample_data", "notes", "exploring_magnets.pdf"))], { type: "application/pdf" }), "exploring_magnets.pdf");
  form.append("title", "Exploring Magnets (assessment e2e)");
  const chapter = chapters.find((c) => /magnet/i.test(c.title));
  if (chapter) form.append("chapter_id", String(chapter.id));
  const note = await call(token, "POST", "/api/notes/upload", form);
  const set = await call(token, "POST", `/api/notes/${note.id}/question-sets`, { count: 8, types: ["mcq", "true_false", "fill_blank", "short"], difficulty: "mixed", section_indices: null });
  const accepted = await call(token, "POST", `/api/question-sets/${set.id}/bulk`, { status: "accepted" });
  await call(token, "PUT", `/api/notes/${note.id}/shares`, { class_ids: [classA.id] });
  const test = await call(token, "POST", "/api/assessments", { title: "Magnets quick test (e2e)", class_id: classA.id, items: accepted.questions.map((q) => ({ question_id: q.id, marks: q.marks })) });
  return { questions: accepted.questions, testId: test.id, noteId: note.id };
}

async function signInAs(page, label) {
  await page.goto(`${APP}/login`);
  await page.getByRole("button", { name: label }).click();
  await page.waitForURL(/\/(student|teacher|parent|admin)$/, { timeout: 15000 });
}
async function signOut(page) {
  await page.getByRole("button", { name: "Sign out" }).click();
  await page.waitForURL(/\/login/);
}

(async () => {
  const { questions, testId, noteId } = await setup();
  const byText = new Map(questions.map((q) => [q.text, q]));
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 1300, height: 900 } });
  const page = await ctx.newPage();
  const problems = [];
  page.on("console", (m) => m.type() === "error" && problems.push("console: " + m.text().slice(0, 200)));
  page.on("pageerror", (e) => problems.push("pageerror: " + e.message.slice(0, 200)));
  page.on("response", (r) => r.status() >= 500 && problems.push(`HTTP ${r.status()} ${r.url()}`));

  // ---- a student from the other class sees nothing
  await signInAs(page, "Student: Rohan (weak)");
  await page.goto(`${APP}/student/tests`);
  await page.getByText("No tests yet").waitFor();
  check("a student in another class sees no tests", true);
  await signOut(page);

  // ---- Aarav takes the test
  await signInAs(page, "Student: Aarav (strong)");
  await page.getByRole("link", { name: "Tests" }).first().click();
  await page.waitForURL(/\/student\/tests$/);
  await page.getByTestId("test-list").waitFor();
  await page.screenshot({ path: `${SHOTS}/t1_list.png` });
  const mine = () => page.getByRole("listitem").filter({ hasText: "Magnets quick test (e2e)" });
  await mine().getByRole("button", { name: "Start test" }).click();
  await page.getByTestId("test-question").first().waitFor();
  const shown = await page.getByTestId("test-question").count();
  check("the test shows every assigned question", shown === questions.length, `${shown} questions`);
  const pageText = await page.locator("main").innerText();
  check("answers are not shown while taking the test", !questions.some((q) => q.type === "short" && pageText.includes(q.answer)));

  // Answer the first 60% correctly and the rest wrongly.
  const cut = Math.ceil(shown * 0.6);
  const expectedLost = [];
  for (let i = 0; i < shown; i++) {
    const qEl = page.getByTestId("test-question").nth(i);
    const q = byText.get((await qEl.innerText()).trim());
    const card = qEl.locator("xpath=ancestor::div[contains(@class,'rounded-xl')][1]");
    const right = i < cut;
    if (!right) expectedLost.push(q.text);
    if (q.options) {
      const pick = right ? q.answer : q.options.find((o) => o !== q.answer);
      await card.getByText(pick, { exact: true }).click();
    } else if (q.type === "fill_blank") {
      await card.getByRole("textbox").fill(right ? q.answer : "banana");
    } else {
      await card.getByRole("textbox").fill(right ? q.answer : "I do not know.");
    }
  }
  await page.screenshot({ path: `${SHOTS}/t2_answered.png`, fullPage: true });
  await page.getByRole("button", { name: "Submit test" }).click();
  await page.getByRole("button", { name: "Yes, submit" }).click();
  await page.getByTestId("score").waitFor({ timeout: 90000 });
  await page.screenshot({ path: `${SHOTS}/t3_report.png`, fullPage: true });
  const scoreText = await page.getByTestId("score").innerText();
  check("submitting shows a score", /\d/.test(scoreText), scoreText);

  // ---- report matches what was answered wrongly
  const review = await page.getByTestId("review-item").evaluateAll((els) => els.map((e) => ({ text: e.querySelector("p.font-medium")?.textContent ?? "", lost: /0 \/ |\d\.?\d? \/ /.test(e.textContent) })));
  const lostOnPage = await page.getByTestId("review-item").evaluateAll((els) =>
    els.map((e) => {
      const m = /(\d+(?:\.\d)?) \/ (\d+(?:\.\d)?)/.exec(e.textContent);
      return { text: e.querySelector("p.font-medium").textContent.replace(/^\d+\.\s*/, ""), lost: m ? Number(m[1]) < Number(m[2]) : false };
    }),
  );
  check("questions answered wrongly lose marks (objective ones are exact)", expectedLost.filter((t) => byText.get(t).type !== "short").every((t) => lostOnPage.find((r) => r.text === t)?.lost === true), `${expectedLost.length} answered wrongly on purpose`);
  const priorityTexts = await page.getByTestId("priority").evaluateAll((els) => els.flatMap((e) => [...e.querySelectorAll("li")].map((li) => li.textContent)));
  const lostSet = new Set(lostOnPage.filter((r) => r.lost).map((r) => r.text));
  check("every question listed under the priorities really lost marks", priorityTexts.length > 0 && priorityTexts.every((t) => lostSet.has(t)), `${priorityTexts.length} listed`);
  const priorityCount = await page.getByTestId("priority").count();
  check("at most 3 priorities are shown", priorityCount >= 1 && priorityCount <= 3, `${priorityCount}`);
  void review;

  // ---- practise a weak topic
  const practice = page.getByRole("link", { name: "Practice this topic" }).first();
  await practice.waitFor();
  const href = await practice.getAttribute("href");
  await practice.click();
  await page.waitForURL(/\/practice\?topic=/, { timeout: 15000 });
  await page.getByText(/Question 1 of/).waitFor({ timeout: 90000 });
  await page.screenshot({ path: `${SHOTS}/t4_practice.png` });
  check("'Practice this topic' opens a quiz about that topic", (await page.getByText(/Questions about “/).count()) === 1, decodeURIComponent(href.split("topic=")[1]));

  // ---- coming back later shows the same results, and a second attempt is not offered
  await page.goto(`${APP}/student/tests`);
  await mine().getByRole("button", { name: "See results" }).click();
  await page.getByTestId("score").waitFor();
  check("reopening a submitted test shows the saved results", (await page.getByTestId("score").innerText()) === scoreText);
  check("there is no way to retake a submitted test", (await page.getByRole("button", { name: "Submit test" }).count()) === 0);
  await signOut(page);

  // ---- the teacher sees the class results
  await signInAs(page, /^Teacher/);
  await page.getByRole("link", { name: "Tests & Results" }).first().click();
  await page.getByTestId("assessment-list").waitFor();
  await page.getByRole("listitem").filter({ hasText: "Magnets quick test (e2e)" }).getByRole("button", { name: "See results" }).click();
  await page.getByTestId("results-table").waitFor();
  await page.screenshot({ path: `${SHOTS}/t5_teacher_results.png`, fullPage: true });
  const rowText = await page.getByRole("row", { name: /Aarav Sharma/ }).innerText();
  check("teacher sees Aarav's submission and score", /Submitted/.test(rowText) && /\d+%/.test(rowText), rowText.replace(/\s+/g, " "));
  check("teacher sees the class topic chart", (await page.locator(".recharts-wrapper").count()) >= 1);
  void noteId;
  void testId;

  check("no console errors or server errors", problems.length === 0, problems.join(" | "));
  await browser.close();
  const failed = results.filter((r) => !r.ok).length;
  console.log(`\n${results.length - failed}/${results.length} checks passed`);
  process.exit(failed ? 1 : 0);
})().catch((e) => {
  console.error("E2E crashed:", e);
  process.exit(1);
});
