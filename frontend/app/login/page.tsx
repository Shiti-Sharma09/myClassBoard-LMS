"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState, type FormEvent } from "react";
import { Logo } from "@/components/AppShell";
import { Button, Card, ErrorBanner, PageLoading, Spinner } from "@/components/ui";
import { api } from "@/lib/api";
import { homeFor, useAuth } from "@/lib/auth";
import type { DemoAccount, Role } from "@/lib/types";

const GROUP_ORDER: Role[] = ["teacher", "student", "parent", "admin"];
const GROUP_TITLE: Record<Role, string> = { teacher: "Teacher", student: "Students", parent: "Parents", admin: "Admin" };

const MODULES = [
  "Question banks generated from your own notes",
  "Handwritten notes turned into editable text",
  "Tests with topic-wise weak-spot reports",
  "Plain-language progress summaries for parents",
  "An adaptive AI interview you can speak or type",
];

export default function LoginPage() {
  const { user, loading, login } = useAuth();
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [demo, setDemo] = useState<DemoAccount[] | null>(null);
  const [demoError, setDemoError] = useState<string | null>(null);

  useEffect(() => {
    if (!loading && user) router.replace(homeFor(user.role));
  }, [loading, user, router]);

  const loadDemoAccounts = useCallback(() => {
    api<DemoAccount[]>("/api/auth/demo-accounts")
      .then((accounts) => {
        setDemo(accounts);
        setDemoError(null);
      })
      .catch((e: Error) => setDemoError(e.message));
  }, []);

  useEffect(() => {
    loadDemoAccounts();
  }, [loadDemoAccounts]);

  async function signIn(e: string, p: string) {
    setError(null);
    setSubmitting(true);
    try {
      const u = await login(e, p);
      router.replace(homeFor(u.role));
    } catch (err) {
      setError((err as Error).message);
      setSubmitting(false);
    }
  }

  function onSubmit(ev: FormEvent) {
    ev.preventDefault();
    void signIn(email, password);
  }

  if (loading || user) return <PageLoading />;

  return (
    <div className="grid min-h-screen lg:grid-cols-[minmax(0,5fr)_minmax(0,6fr)]">
      <aside className="hidden flex-col justify-between bg-gradient-to-br from-indigo-700 via-indigo-600 to-violet-600 p-12 text-white lg:flex">
        <Logo light />
        <div>
          <h1 className="text-3xl font-semibold leading-tight">Less manual work for teachers.<br />Clearer insight for everyone else.</h1>
          <ul className="mt-8 space-y-3 text-indigo-100">
            {MODULES.map((m) => (
              <li key={m} className="flex gap-3">
                <span aria-hidden className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-indigo-200" />
                {m}
              </li>
            ))}
          </ul>
        </div>
        <p className="text-sm text-indigo-200">Proof of concept. All names and marks are synthetic.</p>
      </aside>

      <main className="flex items-center justify-center p-6 sm:p-10">
        <div className="w-full max-w-md space-y-6">
          <div className="lg:hidden">
            <Logo />
          </div>
          <div>
            <h2 className="text-2xl font-semibold text-slate-900">Sign in</h2>
            <p className="mt-1 text-sm text-slate-600">Pick a demo account below, or enter your details.</p>
          </div>

          <form onSubmit={onSubmit} className="space-y-4">
            <label className="block text-sm font-medium text-slate-700">
              Email
              <input
                type="text"
                autoComplete="username"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="mt-1 block w-full rounded-lg border border-slate-300 px-3 py-2 text-slate-900 shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-200"
              />
            </label>
            <label className="block text-sm font-medium text-slate-700">
              Password
              <input
                type="password"
                autoComplete="current-password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="mt-1 block w-full rounded-lg border border-slate-300 px-3 py-2 text-slate-900 shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-200"
              />
            </label>
            {error && <ErrorBanner message={error} />}
            <Button type="submit" loading={submitting} className="w-full">
              Sign in
            </Button>
          </form>

          <Card className="space-y-4">
            <div>
              <h3 className="text-sm font-semibold text-slate-900">Demo accounts</h3>
              <p className="text-xs text-slate-500">One click to sign in. Every demo account uses the password demo1234.</p>
            </div>
            {demoError && <ErrorBanner message={demoError} onRetry={loadDemoAccounts} />}
            {!demo && !demoError && <Spinner label="Loading demo accounts…" />}
            {demo &&
              GROUP_ORDER.map((role) => {
                const accounts = demo.filter((a) => a.role === role);
                if (accounts.length === 0) return null;
                return (
                  <div key={role}>
                    <p className="mb-1.5 text-xs font-medium uppercase tracking-wide text-slate-400">{GROUP_TITLE[role]}</p>
                    <div className="flex flex-wrap gap-2">
                      {accounts.map((a) => (
                        <button
                          key={a.email}
                          disabled={submitting}
                          onClick={() => void signIn(a.email, a.password)}
                          className="rounded-lg bg-slate-50 px-3 py-1.5 text-sm text-slate-700 ring-1 ring-slate-200 transition hover:bg-indigo-50 hover:text-indigo-700 hover:ring-indigo-200 disabled:opacity-60"
                        >
                          {a.label}
                        </button>
                      ))}
                    </div>
                  </div>
                );
              })}
          </Card>
        </div>
      </main>
    </div>
  );
}
