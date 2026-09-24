"use client";

import { NoteView } from "@/components/notes/NoteView";
import { useLibraryRole, useNoteId } from "@/lib/useLibraryRole";

export default function NotePage() {
  return <NoteView role={useLibraryRole()} noteId={useNoteId()} />;
}
