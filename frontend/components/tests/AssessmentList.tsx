"use client";

import Link from "next/link";
import { Button, Card, EmptyState, ErrorBanner, PageLoading } from "@/components/ui";
import { api } from "@/lib/api";
import { useLoad } from "@/lib/hooks";
import { formatDate } from "@/lib/notes";

interface Assessment {
  id: number;
  title: string;
  class_name: string;
  question_count: number;
  total_marks: number;
  created_at: string;
}

export function AssessmentList() {
  const { data, error, loading, reload } = useLoad("assessments", () => api<Assessment[]>("/api/assessments"));
  if (error) return <ErrorBanner message={error} onRetry={reload} />;
  if (loading || !data) return <PageLoading label="Loading tests…" />;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900">Tests & Results</h1>
        <p className="mt-1 text-sm text-slate-500">Tests you have given to a class. Open one to see who took it and which topics were hard.</p>
      </div>
      {data.length === 0 ? (
        <EmptyState
          title="No tests assigned yet"
          message="Pick questions in the Question Bank and choose “Assign as test”."
          action={
            <Link href="/teacher/questions">
              <Button>Open Question Bank</Button>
            </Link>
          }
        />
      ) : (
        <ul className="space-y-3" data-testid="assessment-list">
          {data.map((a) => (
            <li key={a.id}>
              <Card className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <p className="font-semibold text-slate-900">{a.title}</p>
                  <p className="text-sm text-slate-500">
                    Class {a.class_name} · {a.question_count} questions · {a.total_marks} marks · {formatDate(a.created_at)}
                  </p>
                </div>
                <Link href={`/teacher/tests/${a.id}`}>
                  <Button variant="secondary">See results</Button>
                </Link>
              </Card>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
