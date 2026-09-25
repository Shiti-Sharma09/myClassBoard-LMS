import { apiBlob } from "@/lib/api";

export interface NoteSummary {
  id: number;
  title: string;
  subject: string;
  chapter_id: number | null;
  chapter_title: string | null;
  topic: string | null;
  source_type: "ocr" | "typed" | "upload";
  status: "draft" | "saved";
  owner_name: string;
  is_mine: boolean;
  shared_with: string[];
  page_count: number;
  word_count: number;
  snippet: string;
  created_at: string;
}

export interface NoteDetail extends NoteSummary {
  text: string;
  can_edit: boolean;
}

export interface Chapter {
  id: number;
  number: number;
  title: string;
}

export interface ClassInfo {
  id: number;
  name: string;
}

export interface PracticeQuestion {
  question: string;
  options: string[];
  correct_index: number;
  explanation: string;
}

export const SOURCE_LABEL: Record<NoteSummary["source_type"], string> = {
  ocr: "Handwritten",
  typed: "Typed",
  upload: "Uploaded",
};

export type LibraryRole = "teacher" | "student";

export function isLibraryRole(role: string | undefined): role is LibraryRole {
  return role === "teacher" || role === "student";
}

/** Splits OCR text into plain and "[?uncertain?]" parts so the editor can highlight the latter. */
export function splitUncertain(text: string): Array<{ text: string; uncertain: boolean }> {
  const parts: Array<{ text: string; uncertain: boolean }> = [];
  const pattern = /\[\?(.+?)\?\]/g;
  let last = 0;
  for (const match of text.matchAll(pattern)) {
    if (match.index > last) parts.push({ text: text.slice(last, match.index), uncertain: false });
    parts.push({ text: match[1], uncertain: true });
    last = match.index + match[0].length;
  }
  if (last < text.length) parts.push({ text: text.slice(last), uncertain: false });
  return parts;
}

/** Downloads a file from the API. Plain links can't do this because they don't carry the login token. */
export async function downloadFromApi(path: string, fallbackName: string, options?: Parameters<typeof apiBlob>[1]): Promise<void> {
  const { blob, filename } = await apiBlob(path, options);
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename === "download" ? fallbackName : filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" });
}
