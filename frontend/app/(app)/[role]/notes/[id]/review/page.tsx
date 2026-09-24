"use client";

import { ReviewNote } from "@/components/notes/ReviewNote";
import { useLibraryRole, useNoteId } from "@/lib/useLibraryRole";

export default function ReviewNotePage() {
  return <ReviewNote role={useLibraryRole()} noteId={useNoteId()} />;
}
