"use client";

import { Suspense } from "react";
import { NewNote } from "@/components/notes/NewNote";
import { PageLoading } from "@/components/ui";
import { useLibraryRole } from "@/lib/useLibraryRole";

export default function NewNotePage() {
  const role = useLibraryRole();
  return (
    <Suspense fallback={<PageLoading />}>
      <NewNote role={role} />
    </Suspense>
  );
}
