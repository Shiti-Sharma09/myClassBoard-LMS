"use client";

import Link from "next/link";
import { useState } from "react";
import { Button, Card, ErrorBanner, Spinner, cx } from "@/components/ui";
import { api } from "@/lib/api";
import { useLoad } from "@/lib/hooks";
import type { PracticeQuestion } from "@/lib/notes";

function Quiz({ questions, noteHref, onAgain }: { questions: PracticeQuestion[]; noteHref: string; onAgain: () => void }) {
  const [index, setIndex] = useState(0);
  const [picked, setPicked] = useState<number | null>(null);
  const [score, setScore] = useState(0);

  if (index >= questions.length) {
    const message =
      score === questions.length
        ? "Perfect score. Great work!"
        : score >= questions.length / 2
          ? "Nicely done. Read over the ones you missed and try again."
          : "Good effort. Read your note again, then try a new quiz.";
    return (
      <Card className="space-y-4 py-10 text-center">
        <p className="text-4xl font-semibold text-indigo-600">
          {score} / {questions.length}
        </p>
        <p className="text-slate-700">{message}</p>
        <div className="flex justify-center gap-3">
          <Button onClick={onAgain}>New quiz</Button>
          <Link href={noteHref}>
            <Button variant="secondary">Back to note</Button>
          </Link>
        </div>
      </Card>
    );
  }

  const q = questions[index];
  const answered = picked !== null;

  function choose(i: number) {
    if (answered) return;
    setPicked(i);
    if (i === q.correct_index) setScore((s) => s + 1);
  }

  return (
    <Card className="space-y-5">
      <p className="text-sm text-slate-500">
        Question {index + 1} of {questions.length}
      </p>
      <h2 className="text-lg font-semibold text-slate-900">{q.question}</h2>
      <ul className="space-y-2">
        {q.options.map((option, i) => {
          const isCorrect = i === q.correct_index;
          const isPicked = i === picked;
          return (
            <li key={i}>
              <button
                onClick={() => choose(i)}
                disabled={answered}
                className={cx(
                  "w-full rounded-lg border px-4 py-3 text-left text-sm transition",
                  !answered && "border-slate-300 bg-white hover:border-indigo-400 hover:bg-indigo-50",
                  answered && isCorrect && "border-emerald-400 bg-emerald-50 text-emerald-900",
                  answered && isPicked && !isCorrect && "border-red-300 bg-red-50 text-red-900",
                  answered && !isCorrect && !isPicked && "border-slate-200 bg-white text-slate-400",
                )}
              >
                {option}
                {answered && isCorrect && <span className="ml-2 font-medium">✓</span>}
              </button>
            </li>
          );
        })}
      </ul>
      {answered && (
        <div className="space-y-3">
          <p className="rounded-lg bg-slate-100 px-4 py-3 text-sm text-slate-700">
            <strong className="font-medium">{picked === q.correct_index ? "Correct. " : "Not quite. "}</strong>
            {q.explanation}
          </p>
          <Button
            onClick={() => {
              setIndex(index + 1);
              setPicked(null);
            }}
          >
            {index + 1 === questions.length ? "See my score" : "Next question"}
          </Button>
        </div>
      )}
    </Card>
  );
}

export function PracticeQuiz({ noteId, noteHref, topic }: { noteId: number; noteHref: string; topic?: string }) {
  const [round, setRound] = useState(0);
  const { data, error, loading, reload } = useLoad(`practice:${noteId}:${topic ?? ""}:${round}`, () =>
    api<{ questions: PracticeQuestion[] }>(`/api/notes/${noteId}/practice`, { method: "POST", json: topic ? { topic } : undefined }),
  );

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <div>
        <Link href={noteHref} className="text-sm text-indigo-600 hover:underline">
          ← Back to note
        </Link>
        <h1 className="mt-2 text-2xl font-semibold text-slate-900">Practice quiz</h1>
        <p className="mt-1 text-sm text-slate-500">
          {topic ? `Questions about “${topic}”, made from your note.` : "Questions made from your note,"} Just for practice. Nothing here is graded or shared.
        </p>
      </div>

      {error && <ErrorBanner message={error} onRetry={reload} />}
      {loading && !error && (
        <Card className="flex flex-col items-center gap-3 py-12">
          <Spinner size="lg" />
          <p className="text-sm text-slate-600">Making your quiz…</p>
        </Card>
      )}
      {data && !loading && <Quiz key={round} questions={data.questions} noteHref={noteHref} onAgain={() => setRound((r) => r + 1)} />}
    </div>
  );
}
