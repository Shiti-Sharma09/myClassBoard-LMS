"use client";

import { useState } from "react";
import { Badge, Button, ErrorBanner, cx } from "@/components/ui";
import { api } from "@/lib/api";
import { BLOOMS, DIFFICULTIES, TYPE_LABEL, difficultyTone, type Question, type QuestionPatch } from "@/lib/questions";

const FIELD = "w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500";

function Editor({ q, onSave, onCancel }: { q: Question; onSave: (patch: QuestionPatch) => Promise<void>; onCancel: () => void }) {
  const [text, setText] = useState(q.text);
  const [options, setOptions] = useState(q.options ?? []);
  const [answer, setAnswer] = useState(q.answer);
  const [explanation, setExplanation] = useState(q.explanation);
  const [difficulty, setDifficulty] = useState(q.difficulty);
  const [bloom, setBloom] = useState(q.bloom);
  const [marks, setMarks] = useState(String(q.marks));
  const [saving, setSaving] = useState(false);
  const isMcq = q.type === "mcq";

  async function save() {
    setSaving(true);
    const patch: QuestionPatch = { text, answer, explanation, difficulty, bloom, marks: Number(marks) };
    if (isMcq) patch.options = options;
    await onSave(patch); // the parent shows any error and keeps this editor open
    setSaving(false);
  }

  return (
    <div className="space-y-3">
      <label className="block text-sm font-medium text-slate-700">
        Question
        <textarea aria-label="Question text" className={cx(FIELD, "mt-1")} rows={3} value={text} onChange={(e) => setText(e.target.value)} />
      </label>
      {isMcq && (
        <div className="space-y-2">
          <p className="text-sm font-medium text-slate-700">Options (pick the correct one)</p>
          {options.map((option, i) => (
            <div key={i} className="flex items-center gap-2">
              <input type="radio" name={`correct-${q.id}`} aria-label={`Option ${i + 1} is correct`} checked={answer === option} onChange={() => setAnswer(option)} />
              <input
                aria-label={`Option ${i + 1}`}
                className={FIELD}
                value={option}
                onChange={(e) => {
                  const next = [...options];
                  next[i] = e.target.value;
                  if (answer === option) setAnswer(e.target.value);
                  setOptions(next);
                }}
              />
            </div>
          ))}
        </div>
      )}
      {!isMcq && (
        <label className="block text-sm font-medium text-slate-700">
          Answer
          {q.type === "true_false" ? (
            <select aria-label="Answer" className={cx(FIELD, "mt-1")} value={answer} onChange={(e) => setAnswer(e.target.value)}>
              <option>True</option>
              <option>False</option>
            </select>
          ) : (
            <textarea aria-label="Answer" className={cx(FIELD, "mt-1")} rows={q.type === "long" ? 4 : 2} value={answer} onChange={(e) => setAnswer(e.target.value)} />
          )}
        </label>
      )}
      <label className="block text-sm font-medium text-slate-700">
        Explanation
        <textarea aria-label="Explanation" className={cx(FIELD, "mt-1")} rows={2} value={explanation} onChange={(e) => setExplanation(e.target.value)} />
      </label>
      <div className="flex flex-wrap gap-3">
        <label className="text-sm font-medium text-slate-700">
          Difficulty
          <select className={cx(FIELD, "mt-1")} value={difficulty} onChange={(e) => setDifficulty(e.target.value)}>
            {DIFFICULTIES.map((d) => (
              <option key={d}>{d}</option>
            ))}
          </select>
        </label>
        <label className="text-sm font-medium text-slate-700">
          Bloom level
          <select className={cx(FIELD, "mt-1")} value={bloom} onChange={(e) => setBloom(e.target.value)}>
            {BLOOMS.map((b) => (
              <option key={b}>{b}</option>
            ))}
          </select>
        </label>
        <label className="text-sm font-medium text-slate-700">
          Marks
          <input type="number" min={0} step={0.5} className={cx(FIELD, "mt-1 w-24")} value={marks} onChange={(e) => setMarks(e.target.value)} />
        </label>
      </div>
      <div className="flex gap-2">
        <Button onClick={save} loading={saving}>
          Save changes
        </Button>
        <Button variant="ghost" onClick={onCancel}>
          Cancel
        </Button>
      </div>
    </div>
  );
}

/**
 * One question with its review controls. `onChange` receives the server's copy after every save so the
 * page never shows something the server does not have.
 */
export function QuestionCard({
  q,
  onChange,
  showStatus = true,
  actions,
}: {
  q: Question;
  onChange: (q: Question) => void;
  showStatus?: boolean;
  actions?: "review" | "none";
}) {
  const [editing, setEditing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function patch(body: QuestionPatch): Promise<boolean> {
    setError(null);
    try {
      onChange(await api<Question>(`/api/questions/${q.id}`, { method: "PATCH", json: body }));
      return true;
    } catch (err) {
      setError((err as Error).message);
      return false;
    }
  }

  async function setStatus(status: "accepted" | "discarded" | "draft") {
    setBusy(true);
    await patch({ status });
    setBusy(false);
  }

  const tone = q.status === "accepted" ? "border-emerald-300 bg-emerald-50/40" : q.status === "discarded" ? "border-slate-200 bg-slate-50 opacity-70" : "border-slate-200 bg-white";

  return (
    <div className={cx("rounded-xl border p-4 shadow-sm", tone)} data-testid="question-card" data-status={q.status}>
      <div className="mb-2 flex flex-wrap items-center gap-1.5">
        <Badge tone="indigo">{TYPE_LABEL[q.type]}</Badge>
        <Badge tone={difficultyTone(q.difficulty)}>{q.difficulty}</Badge>
        <Badge>{q.bloom}</Badge>
        <Badge>{q.topic}</Badge>
        <Badge>
          {q.marks} {q.marks === 1 ? "mark" : "marks"}
        </Badge>
        {q.edited && <Badge tone="amber">Edited</Badge>}
        {showStatus && q.status === "accepted" && <Badge tone="green">Accepted</Badge>}
        {showStatus && q.status === "discarded" && <Badge tone="red">Discarded</Badge>}
      </div>

      {editing ? (
        <Editor
          q={q}
          onCancel={() => setEditing(false)}
          onSave={async (body) => {
            if (await patch(body)) setEditing(false);
          }}
        />
      ) : (
        <>
          <p className="whitespace-pre-wrap font-medium text-slate-900">{q.text}</p>
          {q.options && (
            <ol className="mt-2 space-y-1 text-sm text-slate-700">
              {q.options.map((option, i) => (
                <li key={i} className={cx("flex gap-2", option === q.answer && "font-semibold text-emerald-700")}>
                  <span className="w-5 shrink-0">{String.fromCharCode(65 + i)}.</span>
                  <span>
                    {option}
                    {option === q.answer && " ✓"}
                  </span>
                </li>
              ))}
            </ol>
          )}
          <details className="mt-2 text-sm">
            <summary className="cursor-pointer text-indigo-600">Answer and explanation</summary>
            <p className="mt-1 whitespace-pre-wrap text-slate-800">
              <span className="font-medium">Answer:</span> {q.answer}
            </p>
            {q.explanation && <p className="mt-1 text-slate-500">{q.explanation}</p>}
          </details>
        </>
      )}

      {error && (
        <div className="mt-3">
          <ErrorBanner message={error} />
        </div>
      )}

      {actions !== "none" && !editing && (
        <div className="mt-3 flex flex-wrap gap-2">
          {q.status !== "accepted" && (
            <Button onClick={() => setStatus("accepted")} loading={busy}>
              Accept
            </Button>
          )}
          {q.status !== "discarded" && (
            <Button variant="secondary" onClick={() => setStatus("discarded")} disabled={busy}>
              Discard
            </Button>
          )}
          {q.status !== "draft" && (
            <Button variant="ghost" onClick={() => setStatus("draft")} disabled={busy}>
              Undo
            </Button>
          )}
          <Button variant="ghost" onClick={() => setEditing(true)}>
            Edit
          </Button>
        </div>
      )}
    </div>
  );
}
