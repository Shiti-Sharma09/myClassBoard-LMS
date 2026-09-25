"use client";

import { useState } from "react";
import { Button, Card, ErrorBanner, cx } from "@/components/ui";
import { api } from "@/lib/api";
import { useLoad } from "@/lib/hooks";
import { downloadFromApi, type ClassInfo } from "@/lib/notes";
import { TYPES, TYPE_LABEL, type BankItem, type QuestionType } from "@/lib/questions";

const FIELD = "w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500";

interface Section {
  type: QuestionType;
  title: string;
  items: BankItem[];
}

/** Questions are grouped into one section per type, in a fixed order, as school papers usually are. */
function buildSections(items: BankItem[], titles: Record<string, string>): Section[] {
  const present = TYPES.filter((t) => items.some((q) => q.type === t));
  return present.map((type, i) => ({
    type,
    title: titles[type] ?? `Section ${String.fromCharCode(65 + i)}: ${TYPE_LABEL[type]}`,
    items: items.filter((q) => q.type === type),
  }));
}

function PrintablePaper({ header, sections, marks, showKey }: { header: Header; sections: Section[]; marks: (q: BankItem) => number; showKey: boolean }) {
  const total = sections.reduce((sum, s) => sum + s.items.reduce((a, q) => a + marks(q), 0), 0);
  let n = 0;
  return (
    <div className="print-paper hidden text-black print:block">
      <div className="text-center">
        {header.school && <p className="text-lg font-bold">{header.school}</p>}
        <p className="text-base font-semibold">{header.title}</p>
        <p className="text-sm">
          {[header.class_name && `Class ${header.class_name}`, header.subject].filter(Boolean).join(" · ")}
        </p>
      </div>
      <div className="mt-2 flex justify-between border-y border-black py-1 text-sm">
        <span>{header.duration ? `Time: ${header.duration} minutes` : ""}</span>
        <span>Maximum marks: {total}</span>
      </div>
      {header.instructions && <p className="mt-2 whitespace-pre-wrap text-sm italic">{header.instructions}</p>}
      {sections.map((s) => (
        <div key={s.type} className="mt-4">
          <p className="font-semibold">{s.title}</p>
          {s.items.map((q) => (
            <div key={q.id} className="mt-2 break-inside-avoid text-sm">
              <p>
                <span className="font-medium">{++n}.</span> {q.text} <span className="float-right">[{marks(q)}]</span>
              </p>
              {q.options && (
                <ol className="ml-6 mt-1 list-[upper-alpha]">
                  {q.options.map((o, i) => (
                    <li key={i}>{o}</li>
                  ))}
                </ol>
              )}
            </div>
          ))}
        </div>
      ))}
      {showKey && (
        <div className="mt-8 break-before-page">
          <p className="font-bold">Answer key</p>
          {(() => {
            let k = 0;
            return sections.flatMap((s) =>
              s.items.map((q) => (
                <p key={q.id} className="mt-1 text-sm">
                  <span className="font-medium">{++k}.</span> {q.answer}
                </p>
              )),
            );
          })()}
        </div>
      )}
    </div>
  );
}

interface Header {
  school: string;
  title: string;
  class_name: string;
  subject: string;
  duration: string;
  instructions: string;
}

export function PaperBuilder({ items, onRemove, onClear }: { items: BankItem[]; onRemove: (id: number) => void; onClear: () => void }) {
  const [header, setHeader] = useState<Header>({
    school: "",
    title: "Class Test",
    class_name: "6",
    subject: "Science",
    duration: "40",
    instructions: "All questions are compulsory.",
  });
  const [titles, setTitles] = useState<Record<string, string>>({});
  const [markOverrides, setMarkOverrides] = useState<Record<number, string>>({});
  const [includeKey, setIncludeKey] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const classes = useLoad("classes", () => api<ClassInfo[]>("/api/classes"));
  const [classId, setClassId] = useState<number | null>(null);
  const [assigning, setAssigning] = useState(false);

  const marks = (q: BankItem) => {
    const raw = markOverrides[q.id];
    const n = raw === undefined ? q.marks : Number(raw);
    return Number.isFinite(n) && n >= 0 ? n : 0;
  };
  const sections = buildSections(items, titles);
  const total = items.reduce((sum, q) => sum + marks(q), 0);
  const set = (key: keyof Header) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => setHeader({ ...header, [key]: e.target.value });
  const chosenClass = classId ?? classes.data?.[0]?.id ?? null;

  async function downloadDocx() {
    setError(null);
    setNotice(null);
    setBusy(true);
    try {
      await downloadFromApi("/api/papers/docx", "question_paper.docx", {
        method: "POST",
        json: {
          school: header.school,
          title: header.title || "Question paper",
          class_name: header.class_name,
          subject: header.subject,
          duration_minutes: header.duration ? Number(header.duration) : null,
          instructions: header.instructions,
          include_answer_key: includeKey,
          sections: sections.map((s) => ({ title: s.title || TYPE_LABEL[s.type], questions: s.items.map((q) => ({ id: q.id, marks: marks(q) })) })),
        },
      });
    } catch (err) {
      setError((err as Error).message);
    }
    setBusy(false);
  }

  async function assign() {
    if (chosenClass === null) return;
    setError(null);
    setNotice(null);
    setAssigning(true);
    try {
      const made = await api<{ title: string; class_name: string; question_count: number; total_marks: number }>("/api/assessments", {
        method: "POST",
        json: { title: header.title || "Class Test", class_id: chosenClass, items: sections.flatMap((s) => s.items).map((q) => ({ question_id: q.id, marks: marks(q) })) },
      });
      setNotice(`“${made.title}” is now assigned to Class ${made.class_name} (${made.question_count} questions, ${made.total_marks} marks).`);
    } catch (err) {
      setError((err as Error).message);
    }
    setAssigning(false);
  }

  if (items.length === 0) {
    return (
      <Card>
        <h2 className="font-semibold text-slate-900">Question paper</h2>
        <p className="mt-1 text-sm text-slate-500">Tick “Add to paper” on questions in the bank and they will appear here, grouped into sections.</p>
      </Card>
    );
  }

  return (
    <div data-testid="paper-builder">
    <Card className="space-y-5 print:hidden">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h2 className="font-semibold text-slate-900">Question paper</h2>
          <p className="text-sm text-slate-500">
            {items.length} questions · <span data-testid="paper-total">{total}</span> marks
          </p>
        </div>
        <Button variant="ghost" onClick={onClear}>
          Clear
        </Button>
      </div>

      <div className="grid gap-3 sm:grid-cols-2">
        <label className="text-sm font-medium text-slate-700">
          School name
          <input className={cx(FIELD, "mt-1")} value={header.school} onChange={set("school")} placeholder="Optional" />
        </label>
        <label className="text-sm font-medium text-slate-700">
          Paper title
          <input aria-label="Paper title" className={cx(FIELD, "mt-1")} value={header.title} onChange={set("title")} />
        </label>
        <label className="text-sm font-medium text-slate-700">
          Class
          <input className={cx(FIELD, "mt-1")} value={header.class_name} onChange={set("class_name")} />
        </label>
        <label className="text-sm font-medium text-slate-700">
          Time (minutes)
          <input type="number" min={1} className={cx(FIELD, "mt-1")} value={header.duration} onChange={set("duration")} />
        </label>
        <label className="text-sm font-medium text-slate-700 sm:col-span-2">
          Instructions
          <textarea className={cx(FIELD, "mt-1")} rows={2} value={header.instructions} onChange={set("instructions")} />
        </label>
      </div>

      <div className="space-y-4">
        {sections.map((s) => (
          <div key={s.type} className="rounded-lg border border-slate-200 p-3">
            <input
              aria-label={`Title of ${TYPE_LABEL[s.type]} section`}
              className={cx(FIELD, "font-medium")}
              value={s.title}
              onChange={(e) => setTitles({ ...titles, [s.type]: e.target.value })}
            />
            <ul className="mt-2 space-y-2">
              {s.items.map((q) => (
                <li key={q.id} className="flex items-start gap-2 text-sm">
                  <span className="min-w-0 flex-1 text-slate-700">{q.text}</span>
                  <input
                    type="number"
                    min={0}
                    step={0.5}
                    aria-label={`Marks for: ${q.text.slice(0, 40)}`}
                    className="w-16 rounded border border-slate-300 px-2 py-1 text-sm"
                    value={markOverrides[q.id] ?? String(q.marks)}
                    onChange={(e) => setMarkOverrides({ ...markOverrides, [q.id]: e.target.value })}
                  />
                  <button onClick={() => onRemove(q.id)} className="text-slate-400 hover:text-red-600" aria-label="Remove from paper">
                    ✕
                  </button>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>

      <label className="flex items-center gap-2 text-sm text-slate-700">
        <input type="checkbox" checked={includeKey} onChange={(e) => setIncludeKey(e.target.checked)} className="h-4 w-4 rounded border-slate-300 text-indigo-600" />
        Include the answer key
      </label>

      {error && <ErrorBanner message={error} />}
      {notice && (
        <div role="status" className="rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">
          {notice}
        </div>
      )}

      <div className="flex flex-wrap gap-2">
        <Button onClick={downloadDocx} loading={busy}>
          Download DOCX
        </Button>
        <Button variant="secondary" onClick={() => window.print()}>
          Print / Save as PDF
        </Button>
      </div>

      <div className="space-y-2 border-t border-slate-200 pt-4">
        <p className="text-sm font-medium text-slate-700">Or give it to a class as an online test</p>
        <div className="flex flex-wrap items-center gap-2">
          <select aria-label="Class to assign to" className="rounded-lg border border-slate-300 px-3 py-2 text-sm" value={chosenClass ?? ""} onChange={(e) => setClassId(Number(e.target.value))}>
            {classes.data?.map((c) => (
              <option key={c.id} value={c.id}>
                Class {c.name}
              </option>
            ))}
          </select>
          <Button variant="secondary" onClick={assign} loading={assigning} disabled={chosenClass === null}>
            Assign as test
          </Button>
        </div>
        <p className="text-xs text-slate-500">Students in that class will see it under Tests. Objective questions are marked automatically.</p>
      </div>

    </Card>
    <PrintablePaper header={header} sections={sections} marks={marks} showKey={includeKey} />
    </div>
  );
}
