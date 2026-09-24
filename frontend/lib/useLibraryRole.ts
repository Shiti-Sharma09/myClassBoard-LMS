import { notFound, useParams } from "next/navigation";
import { isLibraryRole, type LibraryRole } from "@/lib/notes";

/** Reads /[role]/... from the URL. Only teacher and student have a notes library; anything else is a 404. */
export function useLibraryRole(): LibraryRole {
  const { role } = useParams<{ role: string }>();
  if (!isLibraryRole(role)) notFound();
  return role;
}

/** Reads /[role]/notes/[id]/... as a positive integer, or 404s. */
export function useNoteId(): number {
  const { id } = useParams<{ id: string }>();
  const parsed = Number(id);
  if (!Number.isInteger(parsed) || parsed < 1) notFound();
  return parsed;
}
