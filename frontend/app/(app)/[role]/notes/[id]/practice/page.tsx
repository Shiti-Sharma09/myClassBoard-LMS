"use client";

import { notFound } from "next/navigation";
import { PracticeQuiz } from "@/components/notes/PracticeQuiz";
import { useLibraryRole, useNoteId } from "@/lib/useLibraryRole";

export default function PracticePage() {
  const role = useLibraryRole();
  const noteId = useNoteId();
  if (role !== "student") notFound(); // practice quizzes are for students
  return <PracticeQuiz noteId={noteId} noteHref={`/student/notes/${noteId}`} />;
}
