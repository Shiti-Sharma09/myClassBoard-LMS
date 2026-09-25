"use client";

import { GenerateQuestions } from "@/components/questions/GenerateQuestions";
import { useNoteId } from "@/lib/useLibraryRole";

export default function GenerateQuestionsPage() {
  return <GenerateQuestions noteId={useNoteId()} />;
}
