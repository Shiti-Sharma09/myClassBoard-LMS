"use client";

import { notFound, useParams } from "next/navigation";
import { TestPage } from "@/components/tests/TestPage";

export default function StudentTestPage() {
  const { id } = useParams<{ id: string }>();
  const testId = Number(id);
  if (!Number.isInteger(testId) || testId < 1) notFound();
  return <TestPage testId={testId} />;
}
