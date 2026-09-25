"use client";

import Link from "next/link";
import { useState } from "react";
import { SummaryCharts } from "@/components/summary/SummaryView";
import { Badge, Button, Card, ErrorBanner, PageLoading, cx } from "@/components/ui";
import { api } from "@/lib/api";
import { useLoad } from "@/lib/hooks";
import { formatDate } from "@/lib/notes";
import type { Narrative, SummaryDetail } from "@/lib/summaries";

const FIELD = "mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500";

interface Draft {
  overall: string;
  trend: string;
  strengths: string;
  areas: string;
  tips: string;
}

const lines = (text: string) => text.split("\n").map((l) => l.trim()).filter(Boolean);
const toDraft = (n: Narrative): Draft => ({ overall: n.overall, trend: n.trend, strengths: n.strengths.join("\n"), areas: n.areas_to_work_on.join("\n"), tips: n.home_tips.join("\n") });

function Editor({ detail, onChanged }: { detail: SummaryDetail; onChanged: (d: SummaryDetail) => void }) {
  const narrative = detail.narrative!;
  const [draft, setDraft] = useState<Draft>(() => toDraft(narrative));
  const [busy, setBusy] = useState<"save" | "approve" | "regenerate" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const dirty = JSON.stringify(draft) !== JSON.stringify(toDraft(narrative));

  async function run(kind: "save" | "approve" | "regenerate") {
    setError(null);
    setBusy(kind);
    try {
      const base = `/api/summaries/${detail.student_id}`;
      const next =
        kind === "save"
          ? await api<SummaryDetail>(base, {
              method: "PUT",
              json: { overall: draft.overall, trend: draft.trend, strengths: lines(draft.strengths), areas_to_work_on: lines(draft.areas), home_tips: lines(draft.tips) },
            })
          : await api<SummaryDetail>(`${base}/${kind === "approve" ? "approve" : "generate"}`, { method: "POST" });
      onChanged(next);
      if (next.narrative) setDraft(toDraft(next.narrative));
    } catch (err) {
      setError((err as Error).message);
    }
    setBusy(null);
  }

  const set = (key: keyof Draft) => (e: React.ChangeEvent<HTMLTextAreaElement>) => setDraft({ ...draft, [key]: e.target.value });

  return (
    <Card className="space-y-4">
      {detail.source === "template" && (
        <div role="status" className="rounded-lg border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-700">
          This draft uses simple standard wording: the AI was unavailable, or its text didn&apos;t pass the number check. It is correct, so you can approve it, edit it, or try Regenerate.
        </div>
      )}
      <label className="block text-sm font-medium text-slate-700">
        Overall
        <textarea aria-label="Overall" className={FIELD} rows={3} value={draft.overall} onChange={set("overall")} />
      </label>
      <div className="grid gap-4 sm:grid-cols-2">
        <label className="block text-sm font-medium text-slate-700">
          Doing well (one per line)
          <textarea aria-label="Doing well" className={FIELD} rows={4} value={draft.strengths} onChange={set("strengths")} />
        </label>
        <label className="block text-sm font-medium text-slate-700">
          Topics to practise (one per line)
          <textarea aria-label="Topics to practise" className={FIELD} rows={4} value={draft.areas} onChange={set("areas")} />
        </label>
      </div>
      <label className="block text-sm font-medium text-slate-700">
        Progress over the tests
        <textarea aria-label="Progress over the tests" className={FIELD} rows={2} value={draft.trend} onChange={set("trend")} />
      </label>
      <label className="block text-sm font-medium text-slate-700">
        How to help at home (one per line)
        <textarea aria-label="How to help at home" className={FIELD} rows={3} value={draft.tips} onChange={set("tips")} />
      </label>
      <p className="text-xs text-slate-500">Any figure you type must match the marks; the app checks it when you save.</p>

      {error && <ErrorBanner message={error} />}

      <div className="flex flex-wrap items-center gap-2">
        <Button variant="secondary" onClick={() => run("save")} loading={busy === "save"} disabled={!dirty || busy !== null}>
          Save changes
        </Button>
        <Button onClick={() => run("approve")} loading={busy === "approve"} disabled={dirty || detail.status === "approved" || busy !== null} title={dirty ? "Save your changes first" : undefined}>
          {detail.status === "approved" ? "Approved" : "Approve for parent"}
        </Button>
        <Button variant="ghost" onClick={() => run("regenerate")} loading={busy === "regenerate"} disabled={busy !== null}>
          Regenerate
        </Button>
        {dirty && <span className="text-sm text-amber-700">Unsaved changes</span>}
      </div>
    </Card>
  );
}

export function SummaryReview({ studentId }: { studentId: number }) {
  const { data, error, loading, reload } = useLoad(`summary:${studentId}`, () => api<SummaryDetail>(`/api/summaries/${studentId}`));
  const [local, setLocal] = useState<SummaryDetail | null>(null);
  const [generating, setGenerating] = useState(false);
  const [genError, setGenError] = useState<string | null>(null);

  const back = (
    <Link href="/teacher/summaries" className="text-sm text-indigo-600 hover:underline">
      ← Back to summaries
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
  const detail = local ?? data;
  if (loading || !detail) return <PageLoading label="Loading…" />;

  async function generate() {
    setGenError(null);
    setGenerating(true);
    try {
      setLocal(await api<SummaryDetail>(`/api/summaries/${studentId}/generate`, { method: "POST" }));
    } catch (err) {
      setGenError((err as Error).message);
    }
    setGenerating(false);
  }

  const tone = detail.status === "approved" ? "green" : detail.status === "draft" ? "amber" : "slate";

  return (
    <div className="space-y-6">
      {back}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold text-slate-900">{detail.name}</h1>
          <p className="mt-1 text-sm text-slate-500">
            Class {detail.class_name}
            {detail.approved_at && ` · approved ${formatDate(detail.approved_at)}`}
          </p>
        </div>
        <Badge tone={tone}>{detail.status === "none" ? "No draft yet" : detail.status === "draft" ? "Draft (parent can't see it)" : "Approved (parent can see it)"}</Badge>
      </div>

      {detail.narrative ? (
        <Editor key={`${detail.generated_at}-${detail.status}-${detail.edited}`} detail={detail} onChanged={setLocal} />
      ) : (
        <Card className={cx("space-y-3")}>
          <p className="text-sm text-slate-600">No summary has been written for {detail.name.split(" ")[0]} yet. The charts below show the marks it will be based on.</p>
          {genError && <ErrorBanner message={genError} />}
          <Button onClick={generate} loading={generating}>
            Generate draft
          </Button>
        </Card>
      )}

      {detail.facts && <SummaryCharts facts={detail.facts} />}
    </div>
  );
}
