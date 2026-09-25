"use client";

import { notFound, useSearchParams } from "next/navigation";
import { Suspense } from "react";
import { PracticeQuiz } from "@/components/notes/PracticeQuiz";
import { PageLoading } from "@/components/ui";
import { useLibraryRole, useNoteId } from "@/lib/useLibraryRole";

function Practice() {
  const role = useLibraryRole();
  const noteId = useNoteId();
  const topic = useSearchParams().get("topic")?.slice(0, 200) || undefined;
  if (role !== "student") notFound(); // practice quizzes are for students
  return <PracticeQuiz noteId={noteId} noteHref={`/student/notes/${noteId}`} topic={topic} />;
}

export default function PracticePage() {
  return (
    <Suspense fallback={<PageLoading />}>
      <Practice />
    </Suspense>
  );
}
