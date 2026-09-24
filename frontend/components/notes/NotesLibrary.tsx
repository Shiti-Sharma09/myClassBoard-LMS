"use client";

import Link from "next/link";
import { useState } from "react";
import { Badge, Button, Card, EmptyState, ErrorBanner, PageLoading } from "@/components/ui";
import { api } from "@/lib/api";
import { useLoad } from "@/lib/hooks";
import { formatDate, SOURCE_LABEL, type LibraryRole, type NoteSummary } from "@/lib/notes";

export function NotesLibrary({ role }: { role: LibraryRole }) {
  const [query, setQuery] = useState("");
  const { data, error, loading, reload } = useLoad(
    `q:${query}`,
    () => api<NoteSummary[]>(`/api/notes?q=${encodeURIComponent(query)}`),
    query ? 300 : 0,
  );
  const base = `/${role}/notes`;
  const title = role === "teacher" ? "Notes & OCR" : "My Notes";

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-slate-900">{title}</h1>
          <p className="mt-1 max-w-2xl text-slate-600">
            {role === "teacher"
              ? "Turn handwritten notes into text, keep everything in one library, and share notes with your classes."
              : "Photograph your handwritten notes to turn them into text you can search, edit and practise from."}
          </p>
        </div>
        <div className="flex gap-2">
          <Link href={`${base}/new?mode=typed`}>
            <Button variant="secondary">Add typed note</Button>
          </Link>
          <Link href={`${base}/new`}>
            <Button>Digitise handwriting</Button>
          </Link>
        </div>
      </div>

      <input
        type="search"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder="Search your notes by title or words inside them"
        aria-label="Search notes"
        className="block w-full max-w-md rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-200"
      />

      {error && <ErrorBanner message={error} onRetry={reload} />}
      {loading && !data && <PageLoading label="Loading your notes…" />}

      {data && data.length === 0 && (
        <EmptyState
          title={query ? "No notes match that search" : "No notes yet"}
          message={
            query
              ? "Try a different word, or clear the search."
              : "Photograph a page of handwriting to get started. It takes about 20 seconds per page."
          }
          action={
            !query && (
              <Link href={`${base}/new`}>
                <Button>Digitise handwriting</Button>
              </Link>
            )
          }
        />
      )}

      {data && data.length > 0 && (
        <ul className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {data.map((n) => (
            <li key={n.id}>
              <Link href={`${base}/${n.id}`} className="block h-full">
                <Card className="h-full transition hover:border-indigo-300 hover:shadow">
                  <div className="flex flex-wrap items-center gap-1.5">
                    <Badge tone={n.source_type === "ocr" ? "indigo" : "slate"}>{SOURCE_LABEL[n.source_type]}</Badge>
                    {!n.is_mine && <Badge tone="green">Shared by {n.owner_name}</Badge>}
                    {n.shared_with.length > 0 && <Badge tone="amber">Shared with {n.shared_with.join(", ")}</Badge>}
                  </div>
                  <h2 className="mt-3 font-semibold text-slate-900">{n.title}</h2>
                  <p className="mt-1 text-xs text-slate-500">
                    {[n.chapter_title, n.topic].filter(Boolean).join(" · ") || n.subject}
                  </p>
                  <p className="mt-3 line-clamp-3 text-sm text-slate-600">{n.snippet}</p>
                  <p className="mt-3 text-xs text-slate-400">
                    {formatDate(n.created_at)} · {n.word_count} words
                    {n.page_count > 0 && ` · ${n.page_count} page${n.page_count > 1 ? "s" : ""}`}
                  </p>
                </Card>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
