"use client";

import { useState } from "react";
import { PaperBuilder } from "@/components/questions/PaperBuilder";
import { QuestionCard } from "@/components/questions/QuestionCard";
import { Button, Card, EmptyState, ErrorBanner, PageLoading, cx } from "@/components/ui";
import { api } from "@/lib/api";
import { useLoad } from "@/lib/hooks";
import { BLOOMS, DIFFICULTIES, TYPES, TYPE_LABEL, type BankItem, type BankStats, type BankSubject } from "@/lib/questions";

interface Scope {
  chapter_id: number | null | undefined; // undefined = all chapters, null = notes without a chapter
  chapter_title: string;
  topic: string | null;
}

const ALL: Scope = { chapter_id: undefined, chapter_title: "All chapters", topic: null };
const SELECT = "rounded-lg border border-slate-300 px-3 py-2 text-sm";

function Tree({ tree, scope, onPick }: { tree: BankSubject[]; scope: Scope; onPick: (s: Scope) => void }) {
  return (
    <nav aria-label="Question bank tree" className="space-y-3 text-sm">
      <button onClick={() => onPick(ALL)} className={cx("w-full rounded-md px-2 py-1 text-left font-medium", scope === ALL || (scope.chapter_id === undefined && !scope.topic) ? "bg-indigo-50 text-indigo-700" : "text-slate-700 hover:bg-slate-100")}>
        Everything
      </button>
      {tree.map((subject) => (
        <div key={subject.subject}>
          <p className="px-2 text-xs font-semibold uppercase tracking-wide text-slate-500">
            {subject.subject} ({subject.count})
          </p>
          {subject.chapters.map((chapter) => {
            const chapterOpen = scope.chapter_id === chapter.chapter_id && scope.chapter_id !== undefined;
            return (
              <div key={chapter.chapter_id ?? "none"} className="mt-1">
                <button
                  onClick={() => onPick({ chapter_id: chapter.chapter_id, chapter_title: chapter.chapter_title, topic: null })}
                  className={cx("flex w-full justify-between gap-2 rounded-md px-2 py-1 text-left", chapterOpen && !scope.topic ? "bg-indigo-50 font-medium text-indigo-700" : "text-slate-700 hover:bg-slate-100")}
                >
                  <span>{chapter.chapter_title}</span>
                  <span className="text-slate-400">{chapter.count}</span>
                </button>
                {chapterOpen && (
                  <ul className="ml-3 mt-1 border-l border-slate-200 pl-2">
                    {chapter.topics.map((t) => (
                      <li key={t.topic}>
                        <button
                          onClick={() => onPick({ chapter_id: chapter.chapter_id, chapter_title: chapter.chapter_title, topic: t.topic })}
                          className={cx("flex w-full justify-between gap-2 rounded-md px-2 py-1 text-left", scope.topic === t.topic ? "bg-indigo-50 font-medium text-indigo-700" : "text-slate-600 hover:bg-slate-100")}
                        >
                          <span>{t.topic}</span>
                          <span className="text-slate-400">{t.count}</span>
                        </button>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            );
          })}
        </div>
      ))}
    </nav>
  );
}

export function QuestionBank() {
  const [type, setType] = useState("");
  const [difficulty, setDifficulty] = useState("");
  const [bloom, setBloom] = useState("");
  const [scope, setScope] = useState<Scope>(ALL);
  const [paper, setPaper] = useState<BankItem[]>([]);

  const filters = new URLSearchParams();
  if (type) filters.set("type", type);
  if (difficulty) filters.set("difficulty", difficulty);
  if (bloom) filters.set("bloom", bloom);
  const filterQuery = filters.toString();

  const listParams = new URLSearchParams(filters);
  if (scope.chapter_id === null) listParams.set("no_chapter", "true");
  else if (scope.chapter_id !== undefined) listParams.set("chapter_id", String(scope.chapter_id));
  if (scope.topic) listParams.set("topic", scope.topic);

  const tree = useLoad(`tree:${filterQuery}`, () => api<BankSubject[]>(`/api/question-bank/tree?${filterQuery}`));
  const list = useLoad(`list:${listParams.toString()}`, () => api<BankItem[]>(`/api/question-bank?${listParams.toString()}`));
  const stats = useLoad("stats", () => api<BankStats>("/api/question-bank/stats"));

  const error = tree.error ?? list.error;
  const inPaper = new Set(paper.map((q) => q.id));
  const toggle = (q: BankItem) => setPaper(inPaper.has(q.id) ? paper.filter((p) => p.id !== q.id) : [...paper, q]);
  const filtered = Boolean(type || difficulty || bloom || scope.topic || scope.chapter_id !== undefined);

  function addAll() {
    if (!list.data) return;
    const have = new Set(paper.map((q) => q.id));
    setPaper([...paper, ...list.data.filter((q) => !have.has(q.id))]);
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900">Question Bank</h1>
        <p className="mt-1 text-sm text-slate-500">Questions you accepted, organised by chapter and topic. Pick some to make a paper or an online test.</p>
      </div>

      {stats.data && (
        <p className="text-sm text-slate-600" data-testid="bank-stats">
          {stats.data.accepted} accepted · {stats.data.discarded} discarded · {stats.data.pending} waiting for review
          {stats.data.usable_rate !== null && ` · you kept ${Math.round(stats.data.usable_rate * 100)}% of the questions you reviewed`}
        </p>
      )}

      <div className="flex flex-wrap gap-3">
        <select aria-label="Filter by type" className={SELECT} value={type} onChange={(e) => setType(e.target.value)}>
          <option value="">All types</option>
          {TYPES.map((t) => (
            <option key={t} value={t}>
              {TYPE_LABEL[t]}
            </option>
          ))}
        </select>
        <select aria-label="Filter by difficulty" className={SELECT} value={difficulty} onChange={(e) => setDifficulty(e.target.value)}>
          <option value="">All difficulties</option>
          {DIFFICULTIES.map((d) => (
            <option key={d}>{d}</option>
          ))}
        </select>
        <select aria-label="Filter by Bloom level" className={SELECT} value={bloom} onChange={(e) => setBloom(e.target.value)}>
          <option value="">All Bloom levels</option>
          {BLOOMS.map((b) => (
            <option key={b}>{b}</option>
          ))}
        </select>
        {filtered && (
          <Button
            variant="ghost"
            onClick={() => {
              setType("");
              setDifficulty("");
              setBloom("");
              setScope(ALL);
            }}
          >
            Clear filters
          </Button>
        )}
      </div>

      {error && <ErrorBanner message={error} onRetry={() => { tree.reload(); list.reload(); }} />}

      <div className="grid gap-6 lg:grid-cols-[16rem_1fr]">
        <Card className="h-fit">{tree.data ? tree.data.length > 0 ? <Tree tree={tree.data} scope={scope} onPick={setScope} /> : <p className="text-sm text-slate-500">Nothing here yet.</p> : <PageLoading label="" />}</Card>

        <div className="space-y-4">
          {list.loading || !list.data ? (
            <PageLoading label="Loading questions…" />
          ) : list.data.length === 0 ? (
            <EmptyState
              title={filtered ? "No questions match these filters" : "Your bank is empty"}
              message={filtered ? "Try clearing a filter." : "Open one of your notes, choose “Generate questions”, and accept the ones you like. They will show up here."}
            />
          ) : (
            <>
              <div className="flex items-center justify-between gap-3">
                <p className="text-sm text-slate-600">
                  {list.data.length} questions{scope.topic ? ` · ${scope.topic}` : scope.chapter_id !== undefined ? ` · ${scope.chapter_title}` : ""}
                </p>
                <Button variant="secondary" onClick={addAll}>
                  Add all to paper
                </Button>
              </div>
              {list.data.map((q) => (
                <div key={q.id}>
                  <QuestionCard q={q} onChange={() => {}} showStatus={false} actions="none" />
                  <label className="mt-1 flex items-center gap-2 px-1 text-sm text-slate-700">
                    <input type="checkbox" checked={inPaper.has(q.id)} onChange={() => toggle(q)} className="h-4 w-4 rounded border-slate-300 text-indigo-600" />
                    Add to paper
                    <span className="text-slate-400">· from “{q.note_title}”</span>
                  </label>
                </div>
              ))}
            </>
          )}

          <PaperBuilder items={paper} onRemove={(id) => setPaper(paper.filter((q) => q.id !== id))} onClear={() => setPaper([])} />
        </div>
      </div>
    </div>
  );
}
