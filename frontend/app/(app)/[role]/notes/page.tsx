"use client";

import { NotesLibrary } from "@/components/notes/NotesLibrary";
import { useLibraryRole } from "@/lib/useLibraryRole";

export default function NotesPage() {
  return <NotesLibrary role={useLibraryRole()} />;
}
