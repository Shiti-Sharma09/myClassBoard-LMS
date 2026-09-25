"use client";

import { notFound, useParams } from "next/navigation";
import { ClassResults } from "@/components/tests/ClassResults";

export default function TeacherTestResultsPage() {
  const { id } = useParams<{ id: string }>();
  const testId = Number(id);
  if (!Number.isInteger(testId) || testId < 1) notFound();
  return <ClassResults testId={testId} />;
}
