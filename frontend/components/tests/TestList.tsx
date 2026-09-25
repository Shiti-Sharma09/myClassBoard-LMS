"use client";

import Link from "next/link";
import { Badge, Button, Card, EmptyState, ErrorBanner, PageLoading } from "@/components/ui";
import { api } from "@/lib/api";
import { useLoad } from "@/lib/hooks";
import { formatDate } from "@/lib/notes";
import type { TestRow } from "@/lib/tests";

export function TestList() {
  const { data, error, loading, reload } = useLoad("my-tests", () => api<TestRow[]>("/api/tests"));
  if (error) return <ErrorBanner message={error} onRetry={reload} />;
  if (loading || !data) return <PageLoading label="Loading tests…" />;

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900">Tests</h1>
        <p className="mt-1 text-sm text-slate-500">Tests your teacher has given your class. You can take each one once.</p>
      </div>
      {data.length === 0 ? (
        <EmptyState title="No tests yet" message="When your teacher gives your class a test, it will show up here." />
      ) : (
        <ul className="space-y-3" data-testid="test-list">
          {data.map((t) => (
            <li key={t.id}>
              <Card className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <p className="font-semibold text-slate-900">{t.title}</p>
                  <p className="text-sm text-slate-500">
                    {t.question_count} questions · {t.total_marks} marks · given {formatDate(t.created_at)}
                  </p>
                </div>
                <div className="flex items-center gap-3">
                  {t.status === "done" && (
                    <Badge tone="green">
                      {t.marks} / {t.total_marks} ({t.percent}%)
                    </Badge>
                  )}
                  <Link href={`/student/tests/${t.id}`}>
                    <Button variant={t.status === "done" ? "secondary" : "primary"}>{t.status === "done" ? "See results" : "Start test"}</Button>
                  </Link>
                </div>
              </Card>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
