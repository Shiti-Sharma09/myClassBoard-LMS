"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useMemo, useState, type FormEvent } from "react";
import { Button, Card, ErrorBanner, Spinner, cx } from "@/components/ui";
import { api } from "@/lib/api";
import { useLoad } from "@/lib/hooks";
import type { Chapter, LibraryRole, NoteDetail } from "@/lib/notes";

const MAX_PAGES = 5;
type Mode = "handwritten" | "typed";

function ChapterFields({
  chapterId,
  setChapterId,
  topic,
  setTopic,
}: {
  chapterId: string;
  setChapterId: (v: string) => void;
  topic: string;
  setTopic: (v: string) => void;
}) {
  const { data: chapters } = useLoad("chapters", () => api<Chapter[]>("/api/chapters"));
  const field =
    "mt-1 block w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-200";
  return (
    <div className="grid gap-4 sm:grid-cols-2">
      <label className="block text-sm font-medium text-slate-700">
        Chapter <span className="font-normal text-slate-400">(optional)</span>
        <select value={chapterId} onChange={(e) => setChapterId(e.target.value)} className={field}>
          <option value="">Not sure / none</option>
          {chapters?.map((c) => (
            <option key={c.id} value={c.id}>
              {c.number}. {c.title}
            </option>
          ))}
        </select>
      </label>
      <label className="block text-sm font-medium text-slate-700">
        Topic <span className="font-normal text-slate-400">(optional)</span>
        <input value={topic} onChange={(e) => setTopic(e.target.value)} maxLength={200} placeholder="e.g. Poles of a magnet" className={field} />
      </label>
    </div>
  );
}

export function NewNote({ role }: { role: LibraryRole }) {
  const router = useRouter();
  const params = useSearchParams();
  const [mode, setMode] = useState<Mode>(params.get("mode") === "typed" ? "typed" : "handwritten");
  const [chapterId, setChapterId] = useState("");
  const [topic, setTopic] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const base = `/${role}/notes`;

  // handwritten
  const [photos, setPhotos] = useState<File[]>([]);
  const previews = useMemo(() => photos.map((f) => (f.type.startsWith("image/") ? URL.createObjectURL(f) : null)), [photos]);
  useEffect(() => () => previews.forEach((u) => u && URL.revokeObjectURL(u)), [previews]);

  // typed
  const [title, setTitle] = useState("");
  const [text, setText] = useState("");
  const [document_, setDocument] = useState<File | null>(null);

  function meta(form: FormData) {
    if (chapterId) form.append("chapter_id", chapterId);
    if (topic.trim()) form.append("topic", topic.trim());
  }

  function addPhotos(files: FileList | null) {
    if (!files) return;
    const next = [...photos, ...Array.from(files)];
    if (next.length > MAX_PAGES) setError(`You can upload up to ${MAX_PAGES} pages at a time. The extra files were left out.`);
    else setError(null);
    setPhotos(next.slice(0, MAX_PAGES));
  }

  async function digitise(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      const form = new FormData();
      photos.forEach((f) => form.append("files", f));
      meta(form);
      const note = await api<NoteDetail>("/api/notes/ocr", { method: "POST", body: form });
      router.push(`${base}/${note.id}/review`);
    } catch (err) {
      setError((err as Error).message);
      setBusy(false);
    }
  }

  async function saveTyped(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      let note: NoteDetail;
      if (document_) {
        const form = new FormData();
        form.append("file", document_);
        if (title.trim()) form.append("title", title.trim());
        meta(form);
        note = await api<NoteDetail>("/api/notes/upload", { method: "POST", body: form });
      } else {
        note = await api<NoteDetail>("/api/notes", {
          method: "POST",
          json: { title: title.trim(), text, chapter_id: chapterId ? Number(chapterId) : null, topic: topic.trim() || null },
        });
      }
      router.push(`${base}/${note.id}`);
    } catch (err) {
      setError((err as Error).message);
      setBusy(false);
    }
  }

  const tab = (m: Mode, label: string) => (
    <button
      type="button"
      onClick={() => {
        setMode(m);
        setError(null);
      }}
      disabled={busy}
      className={cx(
        "rounded-lg px-4 py-2 text-sm font-medium transition",
        mode === m ? "bg-indigo-600 text-white" : "bg-white text-slate-600 ring-1 ring-slate-300 hover:bg-slate-50",
      )}
    >
      {label}
    </button>
  );

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <div>
        <Link href={base} className="text-sm text-indigo-600 hover:underline">
          ← Back to notes
        </Link>
        <h1 className="mt-2 text-2xl font-semibold text-slate-900">Add a note</h1>
      </div>

      <div className="flex gap-2">
        {tab("handwritten", "Handwritten (photos or PDF)")}
        {tab("typed", "Typed or document")}
      </div>

      {busy && mode === "handwritten" ? (
        <Card className="flex flex-col items-center gap-3 py-12 text-center">
          <Spinner size="lg" />
          <p className="font-medium text-slate-900">Reading your handwriting…</p>
          <p className="max-w-md text-sm text-slate-500">
            This takes about 20 seconds for each page. Please keep this tab open. You&apos;ll get to check and correct the text next.
          </p>
        </Card>
      ) : mode === "handwritten" ? (
        <form onSubmit={digitise} className="space-y-5">
          <Card className="space-y-4">
            <label className="flex cursor-pointer flex-col items-center gap-2 rounded-xl border-2 border-dashed border-slate-300 px-6 py-10 text-center hover:border-indigo-400 hover:bg-indigo-50/40">
              <span className="text-base font-medium text-slate-800">Choose photos or a PDF of your handwritten pages</span>
              <span className="text-sm text-slate-500">JPG, PNG or PDF. Up to {MAX_PAGES} pages, 10 MB each. On a phone you can take a photo.</span>
              <input
                type="file"
                multiple
                accept="image/jpeg,image/png,image/webp,application/pdf"
                className="sr-only"
                onChange={(e) => {
                  addPhotos(e.target.files);
                  e.target.value = "";
                }}
              />
            </label>

            {photos.length > 0 && (
              <ul className="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-5">
                {photos.map((f, i) => (
                  <li key={`${f.name}-${i}`} className="relative overflow-hidden rounded-lg border border-slate-200 bg-slate-50">
                    {previews[i] ? (
                      // eslint-disable-next-line @next/next/no-img-element
                      <img src={previews[i]!} alt={f.name} className="h-32 w-full object-cover" />
                    ) : (
                      <div className="flex h-32 items-center justify-center text-sm font-medium text-slate-500">PDF</div>
                    )}
                    <p className="truncate px-2 py-1 text-xs text-slate-600">{f.name}</p>
                    <button
                      type="button"
                      onClick={() => setPhotos(photos.filter((_, j) => j !== i))}
                      aria-label={`Remove ${f.name}`}
                      className="absolute right-1 top-1 rounded-full bg-white/90 px-2 text-sm text-slate-700 shadow hover:bg-white"
                    >
                      ×
                    </button>
                  </li>
                ))}
              </ul>
            )}

            <ChapterFields chapterId={chapterId} setChapterId={setChapterId} topic={topic} setTopic={setTopic} />
          </Card>

          <p className="rounded-lg bg-slate-100 px-4 py-3 text-sm text-slate-600">
            <strong className="font-medium text-slate-800">What works best:</strong> English handwriting on ruled or plain paper, in good light. Diagrams
            are not interpreted. You will always get to check and fix the text before it is saved.
          </p>

          {error && <ErrorBanner message={error} />}
          <Button type="submit" disabled={photos.length === 0}>
            Digitise {photos.length > 0 ? `${photos.length} page${photos.length > 1 ? "s" : ""}` : "handwriting"}
          </Button>
        </form>
      ) : (
        <form onSubmit={saveTyped} className="space-y-5">
          <Card className="space-y-4">
            <label className="block text-sm font-medium text-slate-700">
              Title {document_ && <span className="font-normal text-slate-400">(optional, defaults to the file name)</span>}
              <input
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                required={!document_}
                maxLength={200}
                className="mt-1 block w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-200"
              />
            </label>

            <label className="block text-sm font-medium text-slate-700">
              Upload a document <span className="font-normal text-slate-400">(PDF, DOCX or TXT)</span>
              <input
                type="file"
                accept=".pdf,.docx,.txt"
                onChange={(e) => setDocument(e.target.files?.[0] ?? null)}
                className="mt-1 block w-full text-sm text-slate-600 file:mr-3 file:rounded-lg file:border-0 file:bg-indigo-50 file:px-3 file:py-2 file:text-sm file:font-medium file:text-indigo-700 hover:file:bg-indigo-100"
              />
            </label>

            {!document_ && (
              <label className="block text-sm font-medium text-slate-700">
                …or type or paste your note
                <textarea
                  value={text}
                  onChange={(e) => setText(e.target.value)}
                  required
                  rows={10}
                  className="mt-1 block w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-200"
                />
              </label>
            )}

            <ChapterFields chapterId={chapterId} setChapterId={setChapterId} topic={topic} setTopic={setTopic} />
          </Card>
          {error && <ErrorBanner message={error} />}
          <Button type="submit" loading={busy}>
            Save note
          </Button>
        </form>
      )}
    </div>
  );
}
