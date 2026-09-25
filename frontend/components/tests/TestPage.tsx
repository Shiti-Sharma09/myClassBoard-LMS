"use client";

import Link from "next/link";
import { useState } from "react";
import { ReportView } from "@/components/tests/ReportView";
import { Button, Card, ErrorBanner, PageLoading, Spinner, cx } from "@/components/ui";
import { api } from "@/lib/api";
import { useLoad } from "@/lib/hooks";
import { TYPE_LABEL } from "@/lib/questions";
import type { PaperQuestion, Report, TestPaper } from "@/lib/tests";

const FIELD = "w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500";

function Answer({ q, value, onChange }: { q: PaperQuestion; value: string; onChange: (v: string) => void }) {
  if (q.options) {
    return (
      <div className="space-y-2" role="radiogroup" aria-label={`Answer for question ${q.id}`}>
        {q.options.map((option) => (
          <label
            key={option}
            className={cx("flex cursor-pointer items-center gap-3 rounded-lg border px-4 py-2.5 text-sm", value === option ? "border-indigo-500 bg-indigo-50" : "border-slate-300 bg-white hover:border-indigo-300")}
          >
            <input type="radio" name={`q-${q.id}`} checked={value === option} onChange={() => onChange(option)} className="h-4 w-4 text-indigo-600" />
            {option}
          </label>
        ))}
      </div>
    );
  }
  if (q.type === "fill_blank") {
    return <input aria-label="Your answer" className={FIELD} value={value} onChange={(e) => onChange(e.target.value)} placeholder="Type the missing word" />;
  }
  return <textarea aria-label="Your answer" className={FIELD} rows={q.type === "long" ? 6 : 3} value={value} onChange={(e) => onChange(e.target.value)} placeholder="Write your answer" />;
}

function TakeTest({ paper, onDone }: { paper: TestPaper; onDone: (r: Report) => void }) {
  const [answers, setAnswers] = useState<Record<number, string>>({});
  const [confirming, setConfirming] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const answered = paper.questions.filter((q) => (answers[q.id] ?? "").trim() !== "").length;
  const left = paper.questions.length - answered;

  async function submit() {
    setError(null);
    setSubmitting(true);
    try {
      const report = await api<Report>(`/api/tests/${paper.id}/submit`, {
        method: "POST",
        json: { answers: paper.questions.map((q) => ({ question_id: q.id, answer: answers[q.id] ?? "" })) },
      });
      onDone(report);
    } catch (err) {
      setError((err as Error).message);
      setSubmitting(false);
      setConfirming(false);
    }
  }

  return (
    <div className="space-y-5">
      {paper.questions.map((q, i) => (
        <Card key={q.id} className="space-y-3" >
          <div className="flex items-start justify-between gap-3">
            <p className="text-xs font-medium uppercase tracking-wide text-slate-500">
              Question {i + 1} · {TYPE_LABEL[q.type]}
            </p>
            <span className="text-xs text-slate-500">
              {q.marks} {q.marks === 1 ? "mark" : "marks"}
            </span>
          </div>
          <p className="font-medium text-slate-900" data-testid="test-question">
            {q.text}
          </p>
          <Answer q={q} value={answers[q.id] ?? ""} onChange={(v) => setAnswers({ ...answers, [q.id]: v })} />
        </Card>
      ))}

      {error && <ErrorBanner message={error} />}

      <Card className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm text-slate-600">
          {answered} of {paper.questions.length} answered
        </p>
        {submitting ? (
          <Spinner label="Marking your answers… this takes a few seconds" />
        ) : confirming ? (
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-sm text-slate-700">{left > 0 ? `${left} unanswered. Submit anyway?` : "Submit your test? You can't change answers afterwards."}</span>
            <Button onClick={submit}>Yes, submit</Button>
            <Button variant="ghost" onClick={() => setConfirming(false)}>
              Keep working
            </Button>
          </div>
        ) : (
          <Button onClick={() => setConfirming(true)}>Submit test</Button>
        )}
      </Card>
    </div>
  );
}

export function TestPage({ testId }: { testId: number }) {
  const paper = useLoad(`test:${testId}`, () => api<TestPaper>(`/api/tests/${testId}`));
  const submitted = paper.data?.submitted ?? false;
  const saved = useLoad(`report:${testId}:${submitted}`, () => (submitted ? api<Report>(`/api/tests/${testId}/report`) : Promise.resolve(null)));
  const [fresh, setFresh] = useState<Report | null>(null);

  const back = (
    <Link href="/student/tests" className="text-sm text-indigo-600 hover:underline">
      ← Back to tests
    </Link>
  );
  const error = paper.error ?? saved.error;
  if (error) {
    return (
      <div className="space-y-4">
        {back}
        <ErrorBanner message={error} onRetry={() => { paper.reload(); saved.reload(); }} />
      </div>
    );
  }
  if (paper.loading || !paper.data || (submitted && (saved.loading || !saved.data) && !fresh)) return <PageLoading label="Loading test…" />;

  const report = fresh ?? saved.data;
  return (
    <div className="mx-auto max-w-3xl space-y-6">
      {back}
      <div>
        <h1 className="text-2xl font-semibold text-slate-900">{paper.data.title}</h1>
        <p className="mt-1 text-sm text-slate-500">
          {report ? "Your results" : `${paper.data.questions.length} questions · ${paper.data.total_marks} marks`}
        </p>
      </div>
      {report ? <ReportView report={report} /> : <TakeTest paper={paper.data} onDone={setFresh} />}
    </div>
  );
}
