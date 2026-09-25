"use client";

import Link from "next/link";
import { useState } from "react";
import { QuestionCard } from "@/components/questions/QuestionCard";
import { Badge, Button, Card, ErrorBanner, PageLoading, Spinner, cx } from "@/components/ui";
import { api } from "@/lib/api";
import { useLoad } from "@/lib/hooks";
import type { NoteDetail } from "@/lib/notes";
import { TYPES, TYPE_LABEL, VERSION_HINT, type NoteTopic, type Question, type QuestionSet, type QuestionType } from "@/lib/questions";

const MAX_VERSIONS = 3;

function Form({ topics, onGenerate, generating, disabled }: { topics: NoteTopic[]; onGenerate: (body: object) => void; generating: boolean; disabled: boolean }) {
  const [count, setCount] = useState(10);
  const [types, setTypes] = useState<QuestionType[]>(["mcq", "short", "true_false"]);
  const [difficulty, setDifficulty] = useState("mixed");
  // Recap sections restate the main text, so they start unticked.
  const [picked, setPicked] = useState<number[]>(topics.filter((t) => !t.recap).map((t) => t.index));

  const toggle = <T,>(list: T[], item: T) => (list.includes(item) ? list.filter((x) => x !== item) : [...list, item]);
  const valid = types.length > 0 && picked.length > 0 && count >= 1 && count <= 20;

  return (
    <Card className="space-y-5">
      <div className="flex flex-wrap gap-6">
        <label className="text-sm font-medium text-slate-700">
          How many questions
          <input
            type="number"
            min={1}
            max={20}
            value={count}
            onChange={(e) => setCount(Number(e.target.value))}
            className="mt-1 block w-28 rounded-lg border border-slate-300 px-3 py-2 text-sm"
          />
        </label>
        <label className="text-sm font-medium text-slate-700">
          Difficulty
          <select value={difficulty} onChange={(e) => setDifficulty(e.target.value)} className="mt-1 block rounded-lg border border-slate-300 px-3 py-2 text-sm">
            <option value="mixed">Mixed</option>
            <option value="easy">Easy</option>
            <option value="medium">Medium</option>
            <option value="hard">Hard</option>
          </select>
        </label>
      </div>

      <fieldset>
        <legend className="text-sm font-medium text-slate-700">Question types</legend>
        <div className="mt-2 flex flex-wrap gap-x-5 gap-y-2">
          {TYPES.map((t) => (
            <label key={t} className="flex items-center gap-2 text-sm text-slate-700">
              <input type="checkbox" checked={types.includes(t)} onChange={() => setTypes(toggle(types, t))} className="h-4 w-4 rounded border-slate-300 text-indigo-600" />
              {TYPE_LABEL[t]}
            </label>
          ))}
        </div>
      </fieldset>

      {topics.length > 1 && (
        <fieldset>
          <legend className="text-sm font-medium text-slate-700">Parts of the note to use</legend>
          <div className="mt-2 grid gap-2 sm:grid-cols-2">
            {topics.map((t) => (
              <label key={t.index} className="flex items-center gap-2 text-sm text-slate-700">
                <input type="checkbox" checked={picked.includes(t.index)} onChange={() => setPicked(toggle(picked, t.index))} className="h-4 w-4 rounded border-slate-300 text-indigo-600" />
                <span>
                  {t.title} {t.recap && <span className="text-slate-400">(recap)</span>}
                </span>
              </label>
            ))}
          </div>
        </fieldset>
      )}

      <div className="flex flex-wrap items-center gap-3">
        <Button
          loading={generating}
          disabled={!valid || disabled}
          onClick={() => onGenerate({ count, types, difficulty, section_indices: topics.length > 1 ? picked : null })}
        >
          Generate questions
        </Button>
        {generating && <Spinner size="sm" label="Reading your note and writing questions… this takes a few seconds" />}
      </div>
    </Card>
  );
}

function VersionPanel({ set, onChanged, onDeleted }: { set: QuestionSet; onChanged: (s: QuestionSet) => void; onDeleted: () => void }) {
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<"accepted" | "discarded" | "delete" | null>(null);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const pending = set.questions.filter((q) => q.status === "draft").length;
  const accepted = set.questions.filter((q) => q.status === "accepted").length;

  function replace(updated: Question) {
    onChanged({ ...set, questions: set.questions.map((q) => (q.id === updated.id ? updated : q)) });
  }

  async function bulk(status: "accepted" | "discarded") {
    setError(null);
    setBusy(status);
    try {
      onChanged(await api<QuestionSet>(`/api/question-sets/${set.id}/bulk`, { method: "POST", json: { status } }));
    } catch (err) {
      setError((err as Error).message);
    }
    setBusy(null);
  }

  async function remove() {
    setError(null);
    setBusy("delete");
    try {
      await api(`/api/question-sets/${set.id}`, { method: "DELETE" });
      onDeleted();
    } catch (err) {
      setError((err as Error).message);
      setConfirmDelete(false);
    }
    setBusy(null);
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm text-slate-600">
          <span className="font-medium">{set.questions.length}</span> questions · {accepted} accepted · {pending} to review
          {set.generation_seconds != null && <span className="text-slate-400"> · made in {set.generation_seconds}s</span>}
        </p>
        <div className="flex flex-wrap gap-2">
          <Button onClick={() => bulk("accepted")} loading={busy === "accepted"} disabled={pending === 0}>
            Accept all remaining
          </Button>
          <Button variant="secondary" onClick={() => bulk("discarded")} loading={busy === "discarded"} disabled={pending === 0}>
            Discard all remaining
          </Button>
        </div>
      </div>

      {set.shortfall_message && (
        <div role="status" className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
          {set.shortfall_message}
        </div>
      )}
      {error && <ErrorBanner message={error} />}

      <div className="space-y-3">
        {set.questions.map((q) => (
          <QuestionCard key={q.id} q={q} onChange={replace} />
        ))}
      </div>

      <div className="border-t border-slate-200 pt-3">
        {confirmDelete ? (
          <span className="flex flex-wrap items-center gap-2 text-sm text-slate-600">
            Throw away this whole version?
            <Button variant="secondary" onClick={remove} loading={busy === "delete"}>
              Yes, throw away
            </Button>
            <Button variant="ghost" onClick={() => setConfirmDelete(false)}>
              Keep it
            </Button>
          </span>
        ) : (
          <Button variant="ghost" onClick={() => setConfirmDelete(true)}>
            Throw away this version
          </Button>
        )}
      </div>
    </div>
  );
}

export function GenerateQuestions({ noteId }: { noteId: number }) {
  const note = useLoad(`note:${noteId}`, () => api<NoteDetail>(`/api/notes/${noteId}`));
  const topics = useLoad(`topics:${noteId}`, () => api<NoteTopic[]>(`/api/notes/${noteId}/topics`));
  const sets = useLoad(`sets:${noteId}`, () => api<QuestionSet[]>(`/api/notes/${noteId}/question-sets`));
  const [local, setLocal] = useState<QuestionSet[] | null>(null);
  const [active, setActive] = useState<number | null>(null);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadError = note.error ?? topics.error ?? sets.error;
  if (loadError) {
    return (
      <div className="space-y-4">
        <Link href={`/teacher/notes/${noteId}`} className="text-sm text-indigo-600 hover:underline">
          ← Back to note
        </Link>
        <ErrorBanner message={loadError} onRetry={() => { note.reload(); topics.reload(); sets.reload(); }} />
      </div>
    );
  }
  if (note.loading || topics.loading || sets.loading || !note.data || !topics.data || !sets.data) return <PageLoading label="Loading…" />;

  const all = (local ?? sets.data).slice().sort((a, b) => a.version - b.version);
  const current = all.find((s) => s.version === active) ?? all[0];
  const full = all.length >= MAX_VERSIONS;

  async function generate(body: object) {
    setError(null);
    setGenerating(true);
    try {
      const made = await api<QuestionSet>(`/api/notes/${noteId}/question-sets`, { method: "POST", json: body });
      setLocal([...all, made]);
      setActive(made.version);
    } catch (err) {
      setError((err as Error).message);
    }
    setGenerating(false);
  }

  return (
    <div className="space-y-6">
      <Link href={`/teacher/notes/${noteId}`} className="text-sm text-indigo-600 hover:underline">
        ← Back to note
      </Link>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold text-slate-900">Generate questions</h1>
          <p className="mt-1 text-sm text-slate-500">From “{note.data.title}”. You can make up to {MAX_VERSIONS} versions; each one reads a different part of the note.</p>
        </div>
        <Link href="/teacher/questions">
          <Button variant="secondary">Open Question Bank</Button>
        </Link>
      </div>

      {full ? (
        <div role="status" className="rounded-lg border border-slate-200 bg-white px-4 py-3 text-sm text-slate-600">
          You have all {MAX_VERSIONS} versions. Throw one away below if you want a fresh one.
        </div>
      ) : (
        <>
          <p className="text-sm text-slate-600">
            Next version: <span className="font-medium">Version {all.length + 1}</span> ({VERSION_HINT[all.length + 1]})
          </p>
          <Form key={all.length} topics={topics.data} onGenerate={generate} generating={generating} disabled={generating} />
        </>
      )}
      {error && <ErrorBanner message={error} />}

      {current && (
        <div className="space-y-4">
          <div role="tablist" className="flex gap-2 border-b border-slate-200">
            {all.map((s) => (
              <button
                key={s.id}
                role="tab"
                aria-selected={s.id === current.id}
                onClick={() => setActive(s.version)}
                className={cx(
                  "-mb-px border-b-2 px-4 py-2 text-sm font-medium",
                  s.id === current.id ? "border-indigo-600 text-indigo-700" : "border-transparent text-slate-500 hover:text-slate-800",
                )}
              >
                Version {s.version} <Badge>{VERSION_HINT[s.version]}</Badge>
              </button>
            ))}
          </div>
          <VersionPanel
            key={current.id}
            set={current}
            onChanged={(updated) => setLocal(all.map((s) => (s.id === updated.id ? updated : s)))}
            onDeleted={() => {
              setLocal(all.filter((s) => s.id !== current.id));
              setActive(null);
            }}
          />
        </div>
      )}
    </div>
  );
}
