"use client";

import Link from "next/link";
import { Bar, BarChart, CartesianGrid, Cell, LabelList, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Badge, Card, cx } from "@/components/ui";
import { TYPE_LABEL } from "@/lib/questions";
import type { Report } from "@/lib/tests";

const GOOD = "#4f46e5";
const WEAK = "#f59e0b";

export function TopicChart({ data, threshold }: { data: Array<{ topic: string; percent: number }>; threshold: number }) {
  const height = Math.max(160, data.length * 44 + 40);
  return (
    <div style={{ height }} role="img" aria-label="Bar chart of the score in each topic">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} layout="vertical" margin={{ left: 8, right: 40 }}>
          <CartesianGrid strokeDasharray="3 3" horizontal={false} />
          <XAxis type="number" domain={[0, 100]} tick={{ fontSize: 11 }} />
          <YAxis type="category" dataKey="topic" width={130} tick={{ fontSize: 12 }} interval={0} />
          <Tooltip formatter={(v) => [`${v}%`, "Score"]} />
          <ReferenceLine x={threshold} stroke="#94a3b8" strokeDasharray="4 4" />
          <Bar dataKey="percent" radius={[0, 4, 4, 0]} isAnimationActive={false}>
            {data.map((d) => (
              <Cell key={d.topic} fill={d.percent < threshold ? WEAK : GOOD} />
            ))}
            <LabelList dataKey="percent" position="right" formatter={(v) => `${v}%`} style={{ fontSize: 11, fill: "#475569" }} />
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

const fmt = (n: number) => (Number.isInteger(n) ? String(n) : n.toFixed(1));

export function ReportView({ report }: { report: Report }) {
  const verdict = report.percent >= 80 ? "Excellent work!" : report.percent >= report.weak_threshold ? "Good effort. A little more practice will help." : "Keep going. Practising the topics below will help a lot.";
  return (
    <div className="space-y-6">
      <Card className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <p className="text-sm text-slate-500">{report.title}</p>
          <p className="text-4xl font-semibold text-indigo-600" data-testid="score">
            {fmt(report.marks)} / {fmt(report.max_marks)}
          </p>
          <p className="text-sm text-slate-600">
            {report.percent}% · {verdict}
          </p>
        </div>
      </Card>

      {report.ai_fallback && (
        <div role="status" className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
          The AI marker was busy, so your written answers were marked by matching key words. Your teacher can check them.
        </div>
      )}

      <Card className="space-y-3">
        <h2 className="font-semibold text-slate-900">Score by topic</h2>
        <TopicChart data={report.topics.map((t) => ({ topic: t.topic, percent: t.percent }))} threshold={report.weak_threshold} />
        <p className="text-xs text-slate-500">Amber bars are below {report.weak_threshold}%. The dashed line marks {report.weak_threshold}%.</p>
      </Card>

      <Card className="space-y-4">
        <h2 className="font-semibold text-slate-900">Your top priorities</h2>
        {report.priorities.length === 0 ? (
          <p className="text-sm text-slate-600">You got every question right. Brilliant!</p>
        ) : (
          <ol className="space-y-4" data-testid="priorities">
            {report.priorities.map((p, i) => (
              <li key={p.topic} className="rounded-lg border border-amber-200 bg-amber-50/60 p-4" data-testid="priority">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <p className="font-medium text-slate-900">
                      {i + 1}. {p.topic} <span className="text-sm font-normal text-slate-600">· {p.percent}%</span>
                    </p>
                    <p className="mt-1 text-xs font-medium uppercase tracking-wide text-slate-500">Questions to look at again</p>
                    <ul className="mt-1 list-disc pl-5 text-sm text-slate-700">
                      {p.missed.map((m) => (
                        <li key={m.question_id}>{m.text}</li>
                      ))}
                    </ul>
                  </div>
                  {p.note_id !== null && (
                    <div className="flex flex-wrap gap-2">
                      <Link
                        href={`/student/notes/${p.note_id}/practice?topic=${encodeURIComponent(p.topic)}`}
                        className="rounded-lg bg-indigo-600 px-3 py-2 text-sm font-medium text-white hover:bg-indigo-700"
                      >
                        Practice this topic
                      </Link>
                      <Link href={`/student/notes/${p.note_id}`} className="rounded-lg px-3 py-2 text-sm font-medium text-indigo-700 ring-1 ring-indigo-200 hover:bg-indigo-50">
                        Read the note
                      </Link>
                    </div>
                  )}
                </div>
                {p.note_id === null && <p className="mt-2 text-xs text-slate-500">Ask your teacher to share the notes for this topic so you can practise it here.</p>}
              </li>
            ))}
          </ol>
        )}
      </Card>

      <Card className="space-y-3">
        <h2 className="font-semibold text-slate-900">Question by question</h2>
        <ul className="space-y-3">
          {report.questions.map((q, i) => {
            const full = q.marks_awarded >= q.max_marks;
            const none = q.marks_awarded === 0;
            return (
              <li key={q.question_id} className={cx("rounded-lg border p-3 text-sm", full ? "border-emerald-200 bg-emerald-50/50" : none ? "border-red-200 bg-red-50/50" : "border-amber-200 bg-amber-50/50")} data-testid="review-item">
                <div className="flex flex-wrap items-center gap-1.5">
                  <Badge tone="indigo">{TYPE_LABEL[q.type]}</Badge>
                  <Badge>{q.topic}</Badge>
                  <Badge tone={full ? "green" : none ? "red" : "amber"}>
                    {fmt(q.marks_awarded)} / {fmt(q.max_marks)}
                  </Badge>
                  {q.scored_by === "ai" && <Badge>Marked by AI</Badge>}
                  {q.scored_by === "keyword" && <Badge tone="amber">Marked by key words</Badge>}
                </div>
                <p className="mt-2 font-medium text-slate-900">
                  {i + 1}. {q.text}
                </p>
                <p className="mt-1 text-slate-700">
                  <span className="font-medium">Your answer:</span> {q.your_answer.trim() || <em className="text-slate-400">no answer</em>}
                </p>
                {!full && (
                  <p className="mt-1 text-slate-700">
                    <span className="font-medium">Correct answer:</span> {q.correct_answer}
                  </p>
                )}
                {q.feedback && q.scored_by !== "code" && <p className="mt-1 text-slate-600">{q.feedback}</p>}
                {q.explanation && <p className="mt-1 text-xs text-slate-500">{q.explanation}</p>}
              </li>
            );
          })}
        </ul>
      </Card>
    </div>
  );
}
