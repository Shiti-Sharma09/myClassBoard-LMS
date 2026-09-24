"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { AuthImage } from "@/components/AuthImage";
import { Badge, Button, Card, ErrorBanner, PageLoading } from "@/components/ui";
import { api } from "@/lib/api";
import { useLoad } from "@/lib/hooks";
import { downloadFromApi, formatDate, SOURCE_LABEL, type ClassInfo, type LibraryRole, type NoteDetail } from "@/lib/notes";

function SharePanel({ note, onChanged }: { note: NoteDetail; onChanged: (n: NoteDetail) => void }) {
  const { data: classes, error: loadError } = useLoad("classes", () => api<ClassInfo[]>("/api/classes"));
  const [picked, setPicked] = useState<number[] | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  const current = classes?.filter((c) => note.shared_with.includes(c.name)).map((c) => c.id) ?? [];
  const selected = picked ?? current;

  async function save() {
    setError(null);
    setSaved(false);
    setSaving(true);
    try {
      onChanged(await api<NoteDetail>(`/api/notes/${note.id}/shares`, { method: "PUT", json: { class_ids: selected } }));
      setPicked(null);
      setSaved(true);
    } catch (err) {
      setError((err as Error).message);
    }
    setSaving(false);
  }

  return (
    <Card className="space-y-3">
      <div>
        <h2 className="font-semibold text-slate-900">Share with a class</h2>
        <p className="text-sm text-slate-500">Students in the classes you tick can read this note and practise from it. They can&apos;t change it.</p>
      </div>
      {loadError && <ErrorBanner message={loadError} />}
      <div className="flex flex-wrap gap-4">
        {classes?.map((c) => (
          <label key={c.id} className="flex items-center gap-2 text-sm text-slate-700">
            <input
              type="checkbox"
              checked={selected.includes(c.id)}
              onChange={(e) => {
                setSaved(false);
                setPicked(e.target.checked ? [...selected, c.id] : selected.filter((id) => id !== c.id));
              }}
              className="h-4 w-4 rounded border-slate-300 text-indigo-600"
            />
            Class {c.name}
          </label>
        ))}
      </div>
      {error && <ErrorBanner message={error} />}
      <div className="flex items-center gap-3">
        <Button onClick={save} loading={saving} disabled={picked === null}>
          Save sharing
        </Button>
        {saved && <span className="text-sm text-emerald-700">Sharing updated</span>}
      </div>
    </Card>
  );
}

export function NoteView({ role, noteId }: { role: LibraryRole; noteId: number }) {
  const router = useRouter();
  const base = `/${role}/notes`;
  const { data, error, loading, reload } = useLoad(`note:${noteId}`, () => api<NoteDetail>(`/api/notes/${noteId}`));
  const [updated, setUpdated] = useState<NoteDetail | null>(null);
  const [busy, setBusy] = useState<"download" | "delete" | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [confirmDelete, setConfirmDelete] = useState(false);

  if (error) {
    return (
      <div className="space-y-4">
        <Link href={base} className="text-sm text-indigo-600 hover:underline">
          ← Back to notes
        </Link>
        <ErrorBanner message={error} onRetry={reload} />
      </div>
    );
  }
  const note = updated ?? data;
  if (loading || !note) return <PageLoading label="Loading note…" />;

  async function download() {
    setActionError(null);
    setBusy("download");
    try {
      await downloadFromApi(`/api/notes/${noteId}/download`, "note.docx");
    } catch (err) {
      setActionError((err as Error).message);
    }
    setBusy(null);
  }

  async function remove() {
    setBusy("delete");
    try {
      await api(`/api/notes/${noteId}`, { method: "DELETE" });
      router.push(base);
    } catch (err) {
      setActionError((err as Error).message);
      setBusy(null);
    }
  }

  const where = [note.chapter_title, note.topic].filter(Boolean).join(" · ");

  return (
    <div className="space-y-6">
      <Link href={base} className="text-sm text-indigo-600 hover:underline">
        ← Back to notes
      </Link>

      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-1.5">
            <Badge tone={note.source_type === "ocr" ? "indigo" : "slate"}>{SOURCE_LABEL[note.source_type]}</Badge>
            <Badge>{note.subject}</Badge>
            {!note.can_edit && <Badge tone="green">Shared by {note.owner_name}</Badge>}
            {note.status === "draft" && <Badge tone="amber">Draft</Badge>}
          </div>
          <h1 className="mt-2 text-2xl font-semibold text-slate-900">{note.title}</h1>
          <p className="mt-1 text-sm text-slate-500">
            {[where, formatDate(note.created_at), `${note.word_count} words`].filter(Boolean).join(" · ")}
          </p>
        </div>

        <div className="flex flex-wrap gap-2">
          {role === "student" && (
            <Link href={`${base}/${noteId}/practice`}>
              <Button>Practice quiz</Button>
            </Link>
          )}
          {role === "teacher" && (
            <Button variant="secondary" disabled title="Coming with the Question Bank">
              Generate questions (soon)
            </Button>
          )}
          <Button variant="secondary" onClick={download} loading={busy === "download"}>
            Download DOCX
          </Button>
          {note.can_edit && (
            <Link href={`${base}/${noteId}/review`}>
              <Button variant="secondary">{note.status === "draft" ? "Review" : "Edit"}</Button>
            </Link>
          )}
        </div>
      </div>

      {actionError && <ErrorBanner message={actionError} />}

      <Card>
        <div className="whitespace-pre-wrap text-[15px] leading-7 text-slate-800">{note.text}</div>
      </Card>

      {note.page_count > 0 && (
        <details className="group rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
          <summary className="cursor-pointer text-sm font-semibold text-slate-700">
            Original {note.page_count > 1 ? `pages (${note.page_count})` : "page"}
          </summary>
          <div className="mt-4 grid gap-4 sm:grid-cols-2">
            {Array.from({ length: note.page_count }, (_, i) => (
              <AuthImage
                key={i}
                path={`/api/notes/${noteId}/pages/${i + 1}/image`}
                alt={`Original handwritten page ${i + 1}`}
                className="w-full rounded-lg border border-slate-200"
              />
            ))}
          </div>
        </details>
      )}

      {role === "teacher" && note.can_edit && note.status === "saved" && <SharePanel note={note} onChanged={setUpdated} />}

      {note.can_edit && (
        <div className="border-t border-slate-200 pt-4">
          {confirmDelete ? (
            <span className="flex flex-wrap items-center gap-2 text-sm text-slate-600">
              Delete this note for good?
              <Button variant="secondary" onClick={remove} loading={busy === "delete"}>
                Yes, delete
              </Button>
              <Button variant="ghost" onClick={() => setConfirmDelete(false)}>
                Keep it
              </Button>
            </span>
          ) : (
            <Button variant="ghost" onClick={() => setConfirmDelete(true)}>
              Delete note
            </Button>
          )}
        </div>
      )}
    </div>
  );
}
