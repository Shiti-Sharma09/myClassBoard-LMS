"use client";

import { NarrativeCard, SummaryCharts } from "@/components/summary/SummaryView";
import { EmptyState, ErrorBanner, PageLoading } from "@/components/ui";
import { api } from "@/lib/api";
import { formatDate } from "@/lib/notes";
import { useLoad } from "@/lib/hooks";
import type { ChildSummary } from "@/lib/summaries";

export function ParentSummary() {
  const { data, error, loading, reload } = useLoad("my-child-summary", () => api<ChildSummary>("/api/my-child/summary"));
  if (error) return <ErrorBanner message={error} onRetry={reload} />;
  if (loading || !data) return <PageLoading label="Loading progress summary…" />;

  const first = data.child_name.split(" ")[0];
  if (!data.available || !data.narrative || !data.facts) {
    return (
      <div className="space-y-4">
        <h1 className="text-2xl font-semibold text-slate-900">How {first} is doing</h1>
        <EmptyState title="Not shared yet" message={`${first}'s teacher hasn't shared a progress summary yet. It will appear here as soon as it has been reviewed.`} />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900">How {first} is doing</h1>
        <p className="mt-1 text-sm text-slate-500">
          Science, Class 6 · Reviewed by the teacher{data.approved_at ? ` on ${formatDate(data.approved_at)}` : ""} · {data.facts.tests_count} tests
        </p>
      </div>
      <NarrativeCard narrative={data.narrative} />
      <SummaryCharts facts={data.facts} />
    </div>
  );
}
