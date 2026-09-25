// End-to-end walk through Parent Summaries: teacher drafts, edits, approves; the parent sees it and the figures match.
//
//   docker compose up -d --build        (from the repo root, with GROQ_API_KEY set: it makes real AI calls)
//   cd e2e && npm install && npx playwright install chromium && npm run summaries
//
// Starts from a fresh demo database (Admin > Reset, or `docker compose down -v`): it expects no summaries yet.
// Takes a couple of minutes because the bulk step writes a summary for every student in one class.
const { chromium } = require("playwright");
const path = require("path");
const fs = require("fs");

const APP = process.env.APP_URL || "http://localhost:3000";
const API = process.env.API_URL || "http://localhost:8010";
const SHOTS = process.env.SHOTS || path.join(__dirname, "shots");
fs.mkdirSync(SHOTS, { recursive: true });

const results = [];
const check = (name, ok, detail = "") => {
  results.push({ name, ok });
  console.log(`${ok ? "PASS" : "FAIL"}  ${name}${detail ? "  (" + detail + ")" : ""}`);
};

async function apiToken(email) {
  const res = await fetch(`${API}/api/auth/login`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ email, password: "demo1234" }) });
  return (await res.json()).token;
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
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 1400, height: 900 } });
  const page = await ctx.newPage();
  const problems = [];
  page.on("console", (m) => m.type() === "error" && !expected422(m.text()) && problems.push("console: " + m.text().slice(0, 200)));
  page.on("pageerror", (e) => problems.push("pageerror: " + e.message.slice(0, 200)));
  page.on("response", (r) => r.status() >= 500 && problems.push(`HTTP ${r.status()} ${r.url()}`));
  // The one 422 in this walkthrough is the deliberate "invented figure" refusal, so the browser logging it is expected.
  const expected422 = (t) => t.includes("422");

  // ---- the parent sees nothing before approval
  await signInAs(page, "Parent of Aarav");
  await page.goto(`${APP}/parent/summary`);
  await page.getByText("Not shared yet").waitFor();
  check("parent sees 'not shared yet' before approval", true);
  await signOut(page);

  // ---- teacher: open Aarav, generate a draft
  await signInAs(page, /^Teacher/);
  await page.goto(`${APP}/teacher/summaries`);
  await page.getByTestId("summary-table").waitFor();
  await page.screenshot({ path: `${SHOTS}/s1_list.png`, fullPage: true });
  const aaravRow = page.getByRole("row", { name: /Aarav Sharma/ });
  check("student list shows live figures before any draft", /\d+%/.test(await aaravRow.innerText()) && /No draft/.test(await aaravRow.innerText()));
  await aaravRow.getByRole("link", { name: "Open" }).click();
  await page.getByRole("heading", { name: "Aarav Sharma" }).waitFor();
  await page.getByRole("button", { name: "Generate draft" }).click();
  await page.getByRole("textbox", { name: "Overall" }).waitFor({ timeout: 90000 });
  await page.screenshot({ path: `${SHOTS}/s2_draft.png`, fullPage: true });
  check("draft is created with charts from the marks", (await page.locator(".recharts-wrapper").count()) >= 2);

  // ---- a wrong figure typed by the teacher is refused; a fine edit is saved
  const overall = page.getByRole("textbox", { name: "Overall" });
  const original = await overall.inputValue();
  await overall.fill(original + " Scored 4242% in every test.");
  await page.getByRole("button", { name: "Save changes" }).click();
  await page.getByRole("alert").filter({ hasText: "4242" }).waitFor();
  check("an invented figure is refused with a clear message", true);
  await overall.fill(original + " Keep up the good work!");
  await page.getByRole("button", { name: "Save changes" }).click();
  await page.getByText("Unsaved changes").waitFor({ state: "detached" });
  check("a normal edit saves", (await overall.inputValue()).includes("Keep up the good work"));

  await page.getByRole("button", { name: "Approve for parent" }).click();
  await page.getByRole("button", { name: "Approved" }).waitFor();
  check("teacher can approve the summary", await page.getByText("Approved (parent can see it)").isVisible());
  const finalOverall = await overall.inputValue();
  await signOut(page);

  // ---- the parent now sees it, and the figures match the API's computed facts
  await signInAs(page, "Parent of Aarav");
  await page.goto(`${APP}/parent/summary`);
  await page.getByTestId("summary-overall").waitFor();
  await page.waitForSelector(".recharts-wrapper");
  await page.screenshot({ path: `${SHOTS}/s3_parent.png`, fullPage: true });
  check("parent sees the approved text the teacher saved", (await page.getByTestId("summary-overall").innerText()) === finalOverall);
  const token = await apiToken("teacher@demo.school");
  const list = await (await fetch(`${API}/api/summaries?class_id=1`, { headers: { Authorization: `Bearer ${token}` } })).json();
  const aarav = list.find((r) => r.name.startsWith("Aarav"));
  const facts = (await (await fetch(`${API}/api/summaries/${aarav.student_id}`, { headers: { Authorization: `Bearer ${token}` } })).json()).facts;
  check("the overall figure on the parent page matches the computed marks", (await page.getByText(`Overall ${facts.overall_percent}%`).count()) === 1, `${facts.overall_percent}%`);
  const weakShown = await page.getByTestId("weak-topics").locator("li").count().catch(() => 0);
  check("weak topics on the page match the computed list", weakShown === facts.weak_topics.length, `${weakShown} shown`);
  await signOut(page);

  // ---- another parent cannot see it
  await signInAs(page, "Parent of Rohan");
  await page.goto(`${APP}/parent/summary`);
  await page.getByText("Not shared yet").waitFor();
  check("a different child's parent still sees nothing", true);
  await signOut(page);

  // ---- bulk: generate the rest of Class 6-A, then approve all
  await signInAs(page, /^Teacher/);
  await page.goto(`${APP}/teacher/summaries`);
  await page.getByTestId("summary-table").waitFor();
  const bulk = page.getByRole("button", { name: /^Generate drafts/ });
  await bulk.click();
  await page.getByText(/Drafts ready for \d+ of \d+ students/).waitFor({ timeout: 280000 });
  await page.screenshot({ path: `${SHOTS}/s4_bulk_done.png`, fullPage: true });
  check("bulk generation reports how many drafts were made", true, await page.getByText(/Drafts ready for/).innerText());
  await page.getByRole("button", { name: /^Approve all drafts/ }).click();
  await page.getByText(/Approved \d+ summar/).waitFor({ timeout: 15000 });
  await page.waitForFunction(() => !/Draft|No draft/.test(document.querySelector('[data-testid="summary-table"]')?.textContent ?? "x"), null, { timeout: 15000 }).catch(() => {});
  const rowsText = await page.getByTestId("summary-table").innerText();
  await page.screenshot({ path: `${SHOTS}/s5_approved.png`, fullPage: true });
  check("approve-all leaves every student approved", !/Draft|No draft/.test(rowsText) && /Approved/.test(rowsText));

  check("no console errors or server errors", problems.length === 0, problems.join(" | "));
  await browser.close();
  const failed = results.filter((r) => !r.ok).length;
  console.log(`\n${results.length - failed}/${results.length} checks passed`);
  process.exit(failed ? 1 : 0);
})().catch((e) => {
  console.error("E2E crashed:", e);
  process.exit(1);
});
