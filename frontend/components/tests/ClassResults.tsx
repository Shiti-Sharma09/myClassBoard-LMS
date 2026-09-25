"use client";

import Link from "next/link";
import { TopicChart } from "@/components/tests/ReportView";
import { Badge, Card, ErrorBanner, PageLoading } from "@/components/ui";
import { api } from "@/lib/api";
import { useLoad } from "@/lib/hooks";
import type { Results } from "@/lib/tests";

export function ClassResults({ testId }: { testId: number }) {
  const { data, error, loading, reload } = useLoad(`results:${testId}`, () => api<Results>(`/api/assessments/${testId}/results`));
  const back = (
    <Link href="/teacher/tests" className="text-sm text-indigo-600 hover:underline">
      ← Back to tests
    </Link>
  );
  if (error) {
    return (
      <div className="space-y-4">
        {back}
        <ErrorBanner message={error} onRetry={reload} />
      </div>
    );
  }
  if (loading || !data) return <PageLoading label="Loading results…" />;

  return (
    <div className="space-y-6">
      {back}
      <div>
        <h1 className="text-2xl font-semibold text-slate-900">{data.title}</h1>
        <p className="mt-1 text-sm text-slate-500">
          Class {data.class_name} · {data.submitted_count} of {data.student_count} students have taken it · out of {data.max_marks} marks
        </p>
      </div>

      <Card className="overflow-x-auto p-0">
        <table className="w-full text-left text-sm" data-testid="results-table">
          <thead className="border-b border-slate-200 bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
            <tr>
              <th className="px-4 py-3">Student</th>
              <th className="px-4 py-3">Status</th>
              <th className="px-4 py-3">Marks</th>
              <th className="px-4 py-3">Score</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {data.students.map((s) => (
              <tr key={s.student_id}>
                <td className="px-4 py-3 font-medium text-slate-900">{s.name}</td>
                <td className="px-4 py-3">{s.submitted ? <Badge tone="green">Submitted</Badge> : <Badge>Not yet</Badge>}</td>
                <td className="px-4 py-3">{s.marks ?? "-"}</td>
                <td className="px-4 py-3">{s.percent === null ? "-" : `${s.percent}%`}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>

      {data.class_topics.length > 0 && (
        <Card className="space-y-3">
          <h2 className="font-semibold text-slate-900">How the class did by topic</h2>
          <TopicChart data={data.class_topics.map((t) => ({ topic: t.topic, percent: t.percent }))} threshold={60} />
          <p className="text-xs text-slate-500">Topics in amber are below 60% across the students who took the test.</p>
        </Card>
      )}
    </div>
  );
}
