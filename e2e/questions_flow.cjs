// End-to-end walk through the Question Bank as a teacher, in a real (headless) browser.
//
//   docker compose up -d --build        (from the repo root, with GROQ_API_KEY set: it makes real AI calls)
//   cd e2e && npm install && npx playwright install chromium && npm run questions
//
// Uploads a sample PDF note through the API (the upload screen is covered by notes_flow), then drives the
// generator, review, bank, paper builder and "assign as test" screens. Screenshots go to e2e/shots.
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

async function apiUploadNote() {
  const login = await fetch(`${API}/api/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email: "teacher@demo.school", password: "demo1234" }),
  });
  const { token } = await login.json();
  const auth = { Authorization: `Bearer ${token}` };
  const chapters = await (await fetch(`${API}/api/chapters`, { headers: auth })).json();
  const chapter = chapters.find((c) => /magnet/i.test(c.title));
  const form = new FormData();
  form.append("file", new Blob([fs.readFileSync(path.join(__dirname, "..", "sample_data", "notes", "exploring_magnets.pdf"))], { type: "application/pdf" }), "exploring_magnets.pdf");
  form.append("title", "Exploring Magnets (e2e)");
  if (chapter) form.append("chapter_id", String(chapter.id));
  const res = await fetch(`${API}/api/notes/upload`, { method: "POST", headers: auth, body: form });
  if (!res.ok) throw new Error("note upload failed: " + res.status);
  return (await res.json()).id;
}

(async () => {
  const noteId = await apiUploadNote();
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 1400, height: 900 }, acceptDownloads: true });
  const page = await ctx.newPage();
  const problems = [];
  page.on("console", (m) => m.type() === "error" && problems.push("console: " + m.text().slice(0, 200)));
  page.on("pageerror", (e) => problems.push("pageerror: " + e.message.slice(0, 200)));
  page.on("response", (r) => r.status() >= 500 && problems.push(`HTTP ${r.status()} ${r.url()}`));

  await page.goto(`${APP}/login`);
  await page.getByRole("button", { name: /^Teacher/ }).click();
  await page.waitForURL(/\/teacher$/, { timeout: 15000 });

  // ---- generate version 1 from the note page
  await page.goto(`${APP}/teacher/notes/${noteId}`);
  await page.getByRole("link", { name: "Generate questions" }).click();
  await page.waitForURL(/\/questions$/);
  await page.getByRole("heading", { name: "Generate questions" }).waitFor();
  await page.screenshot({ path: `${SHOTS}/q1_form.png`, fullPage: true });
  const started = Date.now();
  await page.getByRole("button", { name: "Generate questions" }).click();
  await page.getByTestId("question-card").first().waitFor({ timeout: 90000 });
  const seconds = (Date.now() - started) / 1000;
  const cards = await page.getByTestId("question-card").count();
  await page.screenshot({ path: `${SHOTS}/q2_version1.png`, fullPage: true });
  check("version 1 produced questions in under 60 s", cards >= 5 && seconds < 60, `${cards} questions in ${seconds.toFixed(1)}s`);

  // ---- edit one question, accept it, accept the rest
  const first = page.getByTestId("question-card").first();
  await first.getByRole("button", { name: "Edit" }).click();
  const box = first.getByLabel("Question text");
  const original = await box.inputValue();
  await box.fill(original + " (edited)");
  await first.getByRole("button", { name: "Save changes" }).click();
  await first.getByText("Edited", { exact: true }).waitFor();
  check("editing a question saves and marks it Edited", (await first.innerText()).includes("(edited)"));

  await first.getByRole("button", { name: "Accept", exact: true }).click();
  await page.locator('[data-testid="question-card"][data-status="accepted"]').first().waitFor();
  await page.getByRole("button", { name: "Discard all remaining" }).waitFor();
  const lastCard = page.getByTestId("question-card").last();
  await lastCard.getByRole("button", { name: "Discard", exact: true }).click();
  await page.locator('[data-testid="question-card"][data-status="discarded"]').first().waitFor();
  await page.getByRole("button", { name: "Accept all remaining" }).click();
  await page.waitForFunction(() => document.querySelectorAll('[data-testid="question-card"][data-status="draft"]').length === 0);
  const accepted = await page.locator('[data-testid="question-card"][data-status="accepted"]').count();
  check("accept / discard / accept-all update the cards", accepted === cards - 1, `${accepted} accepted, 1 discarded`);
  await page.screenshot({ path: `${SHOTS}/q3_reviewed.png`, fullPage: true });

  // ---- version 2 appears as its own tab
  await page.getByRole("button", { name: "Generate questions" }).click();
  await page.getByRole("tab", { name: /Version 2/ }).waitFor({ timeout: 90000 });
  check("a second version gets its own tab", await page.getByRole("tab", { name: /Version 1/ }).isVisible());
  await page.getByRole("button", { name: "Accept all remaining" }).click();
  await page.waitForFunction(() => document.querySelectorAll('[data-testid="question-card"][data-status="draft"]').length === 0);
  await page.screenshot({ path: `${SHOTS}/q4_version2.png`, fullPage: true });

  // ---- the bank
  await page.getByRole("link", { name: "Open Question Bank" }).click();
  await page.waitForURL(/\/teacher\/questions$/);
  await page.getByTestId("question-card").first().waitFor();
  const bankCount = await page.getByTestId("question-card").count();
  check("bank lists the accepted questions", bankCount >= accepted, `${bankCount} in the bank`);
  check("bank shows review statistics", /accepted/.test(await page.getByTestId("bank-stats").innerText()));
  await page.getByRole("navigation", { name: "Question bank tree" }).waitFor();

  await page.getByLabel("Filter by type").selectOption("mcq");
  await page.waitForTimeout(800);
  const badges = await page.getByTestId("question-card").evaluateAll((els) => els.map((e) => e.innerText.includes("Multiple choice")));
  check("type filter only shows multiple-choice questions", badges.length > 0 && badges.every(Boolean), `${badges.length} shown`);
  await page.getByRole("button", { name: "Clear filters" }).click();

  // ---- paper builder
  await page.getByRole("button", { name: "Add all to paper" }).click();
  await page.getByTestId("paper-builder").waitFor();
  const before = Number(await page.getByTestId("paper-total").innerText());
  const marksBox = page.getByLabel(/^Marks for:/).first();
  const oldMarks = Number(await marksBox.inputValue());
  await marksBox.fill(String(oldMarks + 3));
  const after = Number(await page.getByTestId("paper-total").innerText());
  check("editing marks updates the paper total", after === before + 3, `${before} -> ${after}`);
  const sectionTitle = page.getByLabel(/^Title of .* section$/).first();
  await sectionTitle.fill("Part One");
  await page.screenshot({ path: `${SHOTS}/q5_bank_paper.png`, fullPage: true });

  const [download] = await Promise.all([page.waitForEvent("download", { timeout: 20000 }), page.getByRole("button", { name: "Download DOCX" }).click()]);
  const file = path.join(SHOTS, "e2e_paper.docx");
  await download.saveAs(file);
  check("paper downloads as a real DOCX", fs.statSync(file).size > 3000 && fs.readFileSync(file).subarray(0, 2).toString() === "PK", download.suggestedFilename());

  await page.emulateMedia({ media: "print" });
  const printed = await page.locator(".print-paper").isVisible();
  const controlsHidden = !(await page.getByRole("button", { name: "Download DOCX" }).isVisible());
  await page.pdf({ path: path.join(SHOTS, "e2e_paper.pdf"), format: "A4" });
  await page.emulateMedia({ media: "screen" });
  check("print view shows only the paper (Save as PDF works)", printed && controlsHidden && fs.statSync(path.join(SHOTS, "e2e_paper.pdf")).size > 2000);

  // ---- assign as test
  await page.getByRole("button", { name: "Assign as test" }).click();
  await page.getByRole("status").filter({ hasText: "is now assigned to Class" }).waitFor({ timeout: 15000 });
  check("paper can be assigned to a class as a test", true, await page.getByRole("status").filter({ hasText: "assigned" }).innerText());
  await page.screenshot({ path: `${SHOTS}/q6_assigned.png`, fullPage: true });

  check("no console errors or server errors", problems.length === 0, problems.join(" | "));
  await browser.close();
  const failed = results.filter((r) => !r.ok).length;
  console.log(`\n${results.length - failed}/${results.length} checks passed`);
  process.exit(failed ? 1 : 0);
})().catch((e) => {
  console.error("E2E crashed:", e);
  process.exit(1);
});
