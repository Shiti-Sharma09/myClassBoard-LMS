"use client";

import Link from "next/link";
import { useState } from "react";
import { Badge, Button, Card, EmptyState, ErrorBanner, PageLoading } from "@/components/ui";
import { api } from "@/lib/api";
import { useLoad } from "@/lib/hooks";
import type { ClassInfo } from "@/lib/notes";
import { TREND_LABEL, type SummaryRow, type SummaryStatus } from "@/lib/summaries";

const STATUS_BADGE: Record<SummaryStatus, { label: string; tone: "slate" | "amber" | "green" }> = {
  none: { label: "No draft", tone: "slate" },
  draft: { label: "Draft", tone: "amber" },
  approved: { label: "Approved", tone: "green" },
};

export function SummaryList() {
  const classes = useLoad("classes", () => api<ClassInfo[]>("/api/classes"));
  const [picked, setPicked] = useState<number | null>(null);
  const classId = picked ?? classes.data?.[0]?.id ?? null;
  const rows = useLoad(`summaries:${classId}`, () => (classId === null ? Promise.resolve([]) : api<SummaryRow[]>(`/api/summaries?class_id=${classId}`)));

  const [progress, setProgress] = useState<{ done: number; total: number; current: string } | null>(null);
  const [failed, setFailed] = useState<string[]>([]);
  const [notice, setNotice] = useState<string | null>(null);
  const [approving, setApproving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadError = classes.error ?? rows.error;
  if (loadError) return <ErrorBanner message={loadError} onRetry={() => { classes.reload(); rows.reload(); }} />;
  if (classes.loading || !classes.data) return <PageLoading label="Loading…" />;

  const list = rows.data ?? [];
  const missing = list.filter((r) => r.status === "none");
  const drafts = list.filter((r) => r.status === "draft");
  const busy = progress !== null;

  /** One request per student so a slow or failed one never blocks the rest, and the teacher sees progress. */
  async function generateMissing() {
    setError(null);
    setNotice(null);
    setFailed([]);
    const bad: string[] = [];
    for (let i = 0; i < missing.length; i++) {
      setProgress({ done: i, total: missing.length, current: missing[i].name });
      try {
        await api(`/api/summaries/${missing[i].student_id}/generate`, { method: "POST" });
      } catch {
        bad.push(missing[i].name);
      }
    }
    setProgress(null);
    setFailed(bad);
    setNotice(`Drafts ready for ${missing.length - bad.length} of ${missing.length} students. Review them, then approve.`);
    rows.reload();
  }

  async function approveAll() {
    if (classId === null) return;
    setError(null);
    setNotice(null);
    setApproving(true);
    try {
      const done = await api<{ approved: number }>("/api/summaries/approve-all", { method: "POST", json: { class_id: classId } });
      setNotice(`Approved ${done.approved} ${done.approved === 1 ? "summary" : "summaries"}. Parents can see them now.`);
      rows.reload();
    } catch (err) {
      setError((err as Error).message);
    }
    setApproving(false);
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900">Parent Summaries</h1>
        <p className="mt-1 max-w-2xl text-sm text-slate-500">
          The numbers come straight from the marks. The AI only puts them into words, and every figure is checked. Parents see a summary only after you approve it.
        </p>
      </div>

      <div className="flex flex-wrap items-end gap-3">
        <label className="text-sm font-medium text-slate-700">
          Class
          <select aria-label="Class" className="mt-1 block rounded-lg border border-slate-300 px-3 py-2 text-sm" value={classId ?? ""} onChange={(e) => setPicked(Number(e.target.value))} disabled={busy}>
            {classes.data.map((c) => (
              <option key={c.id} value={c.id}>
                Class {c.name}
              </option>
            ))}
          </select>
        </label>
        <Button onClick={generateMissing} disabled={busy || missing.length === 0} loading={busy}>
          Generate drafts ({missing.length} left)
        </Button>
        <Button variant="secondary" onClick={approveAll} loading={approving} disabled={busy || drafts.length === 0}>
          Approve all drafts ({drafts.length})
        </Button>
      </div>

      {progress && (
        <p role="status" className="text-sm text-slate-600">
          Writing summary {progress.done + 1} of {progress.total}: {progress.current}…
        </p>
      )}
      {notice && (
        <div role="status" className="rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">
          {notice}
        </div>
      )}
      {failed.length > 0 && <ErrorBanner message={`Couldn't make a draft for: ${failed.join(", ")}. Open the student and try again.`} />}
      {error && <ErrorBanner message={error} />}

      {rows.loading ? (
        <PageLoading label="Loading students…" />
      ) : list.length === 0 ? (
        <EmptyState title="No students in this class" />
      ) : (
        <Card className="overflow-x-auto p-0">
          <table className="w-full text-left text-sm" data-testid="summary-table">
            <thead className="border-b border-slate-200 bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
              <tr>
                <th className="px-4 py-3">Student</th>
                <th className="px-4 py-3">Overall</th>
                <th className="px-4 py-3">Trend</th>
                <th className="px-4 py-3">Weak topics</th>
                <th className="px-4 py-3">Summary</th>
                <th className="px-4 py-3" />
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {list.map((r) => (
                <tr key={r.student_id}>
                  <td className="px-4 py-3 font-medium text-slate-900">{r.name}</td>
                  <td className="px-4 py-3">{r.overall_percent === null ? "-" : `${r.overall_percent}%`}</td>
                  <td className="px-4 py-3">{r.trend ? TREND_LABEL[r.trend] : "-"}</td>
                  <td className="px-4 py-3">{r.weak_topic_count ?? "-"}</td>
                  <td className="px-4 py-3">
                    <div className="flex flex-wrap items-center gap-1">
                      <Badge tone={STATUS_BADGE[r.status].tone}>{STATUS_BADGE[r.status].label}</Badge>
                      {r.edited && <Badge tone="indigo">Edited</Badge>}
                      {r.source === "template" && <Badge>Basic wording</Badge>}
                    </div>
                  </td>
                  <td className="px-4 py-3 text-right">
                    <Link href={`/teacher/summaries/${r.student_id}`} className="font-medium text-indigo-600 hover:underline">
                      {r.status === "none" ? "Open" : "Review"}
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}
    </div>
  );
}
