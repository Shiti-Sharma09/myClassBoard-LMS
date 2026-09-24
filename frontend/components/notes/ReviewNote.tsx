"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { AuthImage } from "@/components/AuthImage";
import { HighlightEditor, type EditorHandle } from "@/components/notes/HighlightEditor";
import { Badge, Button, Card, ErrorBanner, PageLoading } from "@/components/ui";
import { api } from "@/lib/api";
import { useLoad } from "@/lib/hooks";
import type { Chapter, LibraryRole, NoteDetail } from "@/lib/notes";

const field =
  "mt-1 block w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-200";

/** Original pages beside the extracted text. Words the AI was unsure about are highlighted. */
export function ReviewNote({ role, noteId }: { role: LibraryRole; noteId: number }) {
  const router = useRouter();
  const base = `/${role}/notes`;
  const { data: note, error: loadError, loading, reload } = useLoad(`note:${noteId}`, () => api<NoteDetail>(`/api/notes/${noteId}`));
  const { data: chapters } = useLoad("chapters", () => api<Chapter[]>("/api/chapters"));
  const editor = useRef<EditorHandle>(null);

  const [title, setTitle] = useState<string | null>(null);
  const [chapterId, setChapterId] = useState<string | null>(null);
  const [topic, setTopic] = useState<string | null>(null);
  const [remaining, setRemaining] = useState(0);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [confirmDiscard, setConfirmDiscard] = useState(false);

  // A note shared with you is read-only, so send you to the plain view instead.
  const readOnly = note !== undefined && !note.can_edit;
  useEffect(() => {
    if (readOnly) router.replace(`${base}/${noteId}`);
  }, [readOnly, router, base, noteId]);

  if (loadError) return <ErrorBanner message={loadError} onRetry={reload} />;
  if (loading || !note || readOnly) return <PageLoading label="Loading your note…" />;

  const isDraft = note.status === "draft";
  const titleValue = title ?? note.title;
  const chapterValue = chapterId ?? (note.chapter_id ? String(note.chapter_id) : "");
  const topicValue = topic ?? note.topic ?? "";

  async function save() {
    setError(null);
    setSaving(true);
    try {
      await api<NoteDetail>(`/api/notes/${noteId}`, {
        method: "PATCH",
        json: {
          title: titleValue.trim() || "Untitled note",
          text: editor.current?.getText() ?? note!.text,
          chapter_id: chapterValue ? Number(chapterValue) : null,
          topic: topicValue.trim() || null,
          status: "saved",
        },
      });
      router.push(`${base}/${noteId}`);
    } catch (err) {
      setError((err as Error).message);
      setSaving(false);
    }
  }

  async function discard() {
    setSaving(true);
    try {
      await api(`/api/notes/${noteId}`, { method: "DELETE" });
      router.push(base);
    } catch (err) {
      setError((err as Error).message);
      setSaving(false);
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <Link href={isDraft ? base : `${base}/${noteId}`} className="text-sm text-indigo-600 hover:underline">
          ← {isDraft ? "Back to notes" : "Back to note"}
        </Link>
        <h1 className="mt-2 text-2xl font-semibold text-slate-900">{isDraft ? "Check your digitised note" : "Edit note"}</h1>
        {isDraft && (
          <p className="mt-1 max-w-2xl text-slate-600">
            Compare the text with your original pages and fix anything that&apos;s wrong. Nothing is saved to your library until you press Save.
          </p>
        )}
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        {note.page_count > 0 && (
          <section aria-label="Original pages" className="space-y-3 lg:sticky lg:top-6 lg:max-h-[calc(100vh-3rem)] lg:self-start lg:overflow-y-auto">
            <h2 className="text-sm font-semibold text-slate-700">Your original {note.page_count > 1 ? "pages" : "page"}</h2>
            {Array.from({ length: note.page_count }, (_, i) => (
              <AuthImage
                key={i}
                path={`/api/notes/${noteId}/pages/${i + 1}/image`}
                alt={`Original handwritten page ${i + 1}`}
                className="w-full rounded-lg border border-slate-200 shadow-sm"
              />
            ))}
          </section>
        )}

        <section aria-label="Extracted text" className={note.page_count > 0 ? "space-y-4" : "space-y-4 lg:col-span-2"}>
          <Card className="space-y-4">
            <label className="block text-sm font-medium text-slate-700">
              Title
              <input value={titleValue} onChange={(e) => setTitle(e.target.value)} maxLength={200} className={field} />
            </label>
            <div className="grid gap-4 sm:grid-cols-2">
              <label className="block text-sm font-medium text-slate-700">
                Chapter
                <select value={chapterValue} onChange={(e) => setChapterId(e.target.value)} className={field}>
                  <option value="">None</option>
                  {chapters?.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.number}. {c.title}
                    </option>
                  ))}
                </select>
              </label>
              <label className="block text-sm font-medium text-slate-700">
                Topic
                <input value={topicValue} onChange={(e) => setTopic(e.target.value)} maxLength={200} className={field} />
              </label>
            </div>
          </Card>

          <div>
            <div className="mb-2 flex items-center justify-between gap-3">
              <h2 className="text-sm font-semibold text-slate-700">Text</h2>
              {remaining > 0 ? (
                <Badge tone="amber">{remaining} word{remaining > 1 ? "s" : ""} to check</Badge>
              ) : (
                isDraft && <Badge tone="green">Nothing flagged</Badge>
              )}
            </div>
            <HighlightEditor ref={editor} initialText={note.text} onRemainingChange={setRemaining} />
            <p className="mt-2 text-xs text-slate-500">
              {remaining > 0
                ? "Yellow words may be misread. Click into one and fix it if needed. The highlight goes away once you edit it."
                : "The AI can miss mistakes it isn't aware of, so give it a quick read against your page."}
            </p>
          </div>

          {error && <ErrorBanner message={error} />}
          <div className="flex flex-wrap items-center gap-3">
            <Button onClick={save} loading={saving}>
              {isDraft ? "Save to my notes" : "Save changes"}
            </Button>
            {isDraft &&
              (confirmDiscard ? (
                <span className="flex items-center gap-2 text-sm text-slate-600">
                  Discard this note?
                  <Button variant="secondary" onClick={discard} disabled={saving}>
                    Yes, discard
                  </Button>
                  <Button variant="ghost" onClick={() => setConfirmDiscard(false)}>
                    Keep it
                  </Button>
                </span>
              ) : (
                <Button variant="ghost" onClick={() => setConfirmDiscard(true)} disabled={saving}>
                  Discard
                </Button>
              ))}
          </div>
        </section>
      </div>
    </div>
  );
}
