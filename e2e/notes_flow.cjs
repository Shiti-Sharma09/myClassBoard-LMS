// End-to-end walk through the Notes Library as real users, in a real (headless) browser.
//
//   docker compose up -d --build        (from the repo root, with GROQ_API_KEY set: it makes real AI calls)
//   cd e2e && npm install && npx playwright install chromium && npm run notes
//
// Starts from a freshly seeded database: run `docker compose down -v` first if you have created notes.
// Screenshots go to e2e/shots (git-ignored). Takes about a minute because of the AI rate limit.
const { chromium } = require("playwright");
const path = require("path");

const APP = process.env.APP_URL || "http://localhost:3000";
const SAMPLES = path.join(__dirname, "..", "sample_data", "handwritten");
const SHOTS = process.env.SHOTS || path.join(__dirname, "shots");
require("fs").mkdirSync(SHOTS, { recursive: true });

const results = [];
const check = (name, ok, detail = "") => {
  results.push({ name, ok });
  console.log(`${ok ? "PASS" : "FAIL"}  ${name}${detail ? "  (" + detail + ")" : ""}`);
};

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
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 1400, height: 900 } });
  const page = await ctx.newPage();
  const problems = [];
  page.on("console", (m) => m.type() === "error" && problems.push("console: " + m.text().slice(0, 200)));
  page.on("pageerror", (e) => problems.push("pageerror: " + e.message.slice(0, 200)));
  page.on("response", (r) => r.status() >= 500 && problems.push(`HTTP ${r.status()} ${r.url()}`));

  // ---- login screen
  await page.goto(`${APP}/login`);
  await page.getByRole("heading", { name: "Demo accounts" }).waitFor();
  await page.screenshot({ path: `${SHOTS}/01_login.png` });
  check("login page shows demo accounts", await page.getByRole("button", { name: /Student: Aarav/ }).isVisible());

  // ---- student Aarav: digitise handwriting
  await signInAs(page, "Student: Aarav (strong)");
  await page.getByRole("link", { name: "My Notes" }).first().click();
  await page.waitForURL(/\/student\/notes$/);
  await page.getByText("No notes yet").waitFor();
  await page.screenshot({ path: `${SHOTS}/02_student_notes_empty.png` });
  check("empty library shows a friendly empty state", true);

  await page.getByRole("link", { name: "Digitise handwriting" }).first().click();
  await page.waitForURL(/\/student\/notes\/new/);
  await page.locator('input[type="file"]').setInputFiles(path.join(SAMPLES, "neat_1.jpg"));
  await page.screenshot({ path: `${SHOTS}/03_upload_selected.png` });
  await page.getByRole("button", { name: /Digitise 1 page/ }).click();
  await page.getByText("Reading your handwriting").waitFor();
  await page.screenshot({ path: `${SHOTS}/04_reading.png` });
  await page.waitForURL(/\/student\/notes\/\d+\/review/, { timeout: 120000 });
  await page.getByRole("textbox", { name: "Note text" }).waitFor();
  await page.waitForTimeout(800);
  await page.screenshot({ path: `${SHOTS}/05_review.png`, fullPage: true });
  const ocrText = await page.getByRole("textbox", { name: "Note text" }).innerText();
  check("review screen shows the recognised text", /magnet/i.test(ocrText) && /iron/i.test(ocrText), ocrText.split("\n")[0]);
  check("review screen shows the original page", await page.locator("img[alt^='Original handwritten page']").first().isVisible());

  // edit: change the title, then save
  const noteId = page.url().match(/notes\/(\d+)\/review/)[1];
  await page.getByLabel("Title").fill("My magnet notes");
  await page.getByRole("button", { name: "Save to my notes" }).click();
  await page.waitForURL(new RegExp(`/student/notes/${noteId}$`), { timeout: 15000 });
  await page.getByRole("heading", { name: "My magnet notes" }).waitFor();
  await page.screenshot({ path: `${SHOTS}/06_note_saved.png`, fullPage: true });
  check("saved note opens with the edited title", true);

  // DOCX download works through the authenticated download
  const [download] = await Promise.all([page.waitForEvent("download", { timeout: 15000 }), page.getByRole("button", { name: "Download DOCX" }).click()]);
  check("DOCX download starts", download.suggestedFilename().endsWith(".docx"), download.suggestedFilename());

  // library + search
  await page.goto(`${APP}/student/notes`);
  await page.getByText("My magnet notes").waitFor();
  await page.getByLabel("Search notes").fill("cobalt");
  await page.getByText("My magnet notes").waitFor();
  await page.getByLabel("Search notes").fill("volcano");
  await page.getByText("No notes match that search").waitFor();
  check("search finds text inside notes and shows a message when nothing matches", true);
  await page.screenshot({ path: `${SHOTS}/07_search_none.png` });

  // ---- practice quiz
  await page.goto(`${APP}/student/notes/${noteId}/practice`);
  await page.getByText("Question 1 of").waitFor({ timeout: 90000 });
  await page.screenshot({ path: `${SHOTS}/08_quiz_q1.png` });
  const options = page.locator("ul button");
  await options.first().click();
  await page.getByRole("button", { name: /Next question|See my score/ }).waitFor();
  await page.screenshot({ path: `${SHOTS}/09_quiz_answered.png` });
  check("practice quiz shows a question and instant feedback", true);

  // ---- privacy: Rohan can't see Aarav's note
  await signOut(page);
  await signInAs(page, "Student: Rohan (weak)");
  await page.goto(`${APP}/student/notes`);
  await page.getByText("No notes yet").waitFor();
  check("another student's library is empty", true);
  await page.goto(`${APP}/student/notes/${noteId}`);
  await page.getByText("That note wasn't found.").waitFor();
  await page.screenshot({ path: `${SHOTS}/10_other_student_blocked.png` });
  check("another student cannot open Aarav's note by URL", true);

  // ---- teacher: typed note, share with 6-A
  await signOut(page);
  await signInAs(page, "Teacher (Priya Deshmukh)");
  await page.goto(`${APP}/teacher/notes/new?mode=typed`);
  await page.getByLabel(/^Title/).fill("Separation methods");
  await page.getByLabel("…or type or paste your note").fill(
    "Winnowing separates husk from grains using wind. Sieving separates particles by size. Filtration removes insoluble solids from a liquid. Evaporation recovers a dissolved solid such as salt from sea water. A magnet can pull iron pins out of sand."
  );
  await page.getByRole("button", { name: "Save note" }).click();
  await page.waitForURL(/\/teacher\/notes\/\d+$/);
  await page.getByText("Share with a class").waitFor();
  await page.getByLabel("Class 6-A").check();
  await page.getByRole("button", { name: "Save sharing" }).click();
  await page.getByText("Sharing updated").waitFor();
  await page.screenshot({ path: `${SHOTS}/11_teacher_share.png`, fullPage: true });
  const sharedId = page.url().match(/notes\/(\d+)$/)[1];
  check("teacher can share a note with a class", true);

  // ---- Diya (6-A) sees it read-only; Rohan (6-B) does not
  await signOut(page);
  await signInAs(page, "Student: Diya (average)");
  await page.goto(`${APP}/student/notes`);
  await page.getByText("Separation methods").waitFor();
  await page.getByText(/Shared by Priya/).first().waitFor();
  await page.screenshot({ path: `${SHOTS}/12_student_sees_shared.png` });
  await page.goto(`${APP}/student/notes/${sharedId}`);
  await page.getByRole("heading", { name: "Separation methods" }).waitFor();
  check("shared note is read-only for the student (no Edit or Delete)", (await page.getByRole("button", { name: "Delete note" }).count()) === 0);
  await signOut(page);
  await signInAs(page, "Student: Rohan (weak)");
  await page.goto(`${APP}/student/notes`);
  await page.getByText("No notes yet").waitFor();
  check("a student in another class does not see the shared note", true);

  await browser.close();
  console.log(problems.length ? "\nBrowser problems:\n" + [...new Set(problems)].join("\n") : "\nNo console errors or 5xx responses.");
  const failed = results.filter((r) => !r.ok).length;
  console.log(`\n${results.length - failed}/${results.length} checks passed`);
  process.exit(failed ? 1 : 0);
})().catch((e) => {
  console.error("SCRIPT ERROR:", e.message.split("\n").slice(0, 8).join("\n"));
  process.exit(2);
});
