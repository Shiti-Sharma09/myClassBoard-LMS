"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";
import { api } from "@/lib/api";
import { homeFor, useAuth } from "@/lib/auth";
import { NAV } from "@/lib/nav";
import type { Role } from "@/lib/types";
import { Badge, cx, PageLoading } from "@/components/ui";

const ROLE_LABEL: Record<Role, string> = {
  teacher: "Teacher",
  student: "Student",
  parent: "Parent",
  admin: "Admin",
};

/** Small dot in the header showing whether the API is reachable. Handy before a live demo. */
function ApiStatus() {
  const [ok, setOk] = useState<boolean | null>(null);
  useEffect(() => {
    let cancelled = false;
    api("/api/health")
      .then(() => !cancelled && setOk(true))
      .catch(() => !cancelled && setOk(false));
    return () => {
      cancelled = true;
    };
  }, []);
  if (ok === null) return null;
  return (
    <span className="flex items-center gap-1.5 text-xs text-slate-500" title={ok ? "Server connected" : "Server not reachable"}>
      <span className={cx("h-2 w-2 rounded-full", ok ? "bg-emerald-500" : "bg-red-500")} />
      {ok ? "Connected" : "Offline"}
    </span>
  );
}

export function Logo({ light = false }: { light?: boolean }) {
  return (
    <div className="flex items-center gap-2.5">
      <span className={cx("flex h-9 w-9 items-center justify-center rounded-xl text-base font-bold", light ? "bg-white text-indigo-700" : "bg-indigo-600 text-white")}>
        M
      </span>
      <span className="leading-tight">
        <span className={cx("block text-sm font-semibold", light ? "text-white" : "text-slate-900")}>myClassBoard</span>
        <span className={cx("block text-xs", light ? "text-indigo-200" : "text-slate-500")}>AI Learning Assistant</span>
      </span>
    </div>
  );
}

/** Wraps every signed-in page: redirects visitors who aren't signed in or are in the wrong area. */
export function AppShell({ children }: { children: ReactNode }) {
  const { user, loading, logout } = useAuth();
  const router = useRouter();
  const pathname = usePathname();

  const area = pathname.split("/")[1];
  const wrongArea = user !== null && area !== user.role;

  useEffect(() => {
    if (loading) return;
    if (!user) router.replace("/login");
    else if (wrongArea) router.replace(homeFor(user.role));
  }, [loading, user, wrongArea, router]);

  if (loading || !user || wrongArea) return <PageLoading label="Loading your workspace…" />;

  const items = NAV[user.role];
  const context = user.student?.class_name ?? (user.child ? `${user.child.name}, ${user.child.class_name}` : null);

  return (
    <div className="flex min-h-screen bg-slate-50">
      <aside className="hidden w-64 shrink-0 flex-col border-r border-slate-200 bg-white p-4 md:flex">
        <Logo />
        <nav className="mt-8 flex flex-1 flex-col gap-1" aria-label="Main">
          <Link
            href={homeFor(user.role)}
            className={cx(
              "rounded-lg px-3 py-2 text-sm font-medium",
              pathname === homeFor(user.role) ? "bg-indigo-50 text-indigo-700" : "text-slate-600 hover:bg-slate-100",
            )}
          >
            Dashboard
          </Link>
          {items.map((item) =>
            item.ready ? (
              <Link
                key={item.href}
                href={item.href}
                className={cx(
                  "rounded-lg px-3 py-2 text-sm font-medium",
                  pathname.startsWith(item.href) ? "bg-indigo-50 text-indigo-700" : "text-slate-600 hover:bg-slate-100",
                )}
              >
                {item.label}
              </Link>
            ) : (
              <span key={item.href} className="flex cursor-not-allowed items-center justify-between rounded-lg px-3 py-2 text-sm text-slate-400">
                {item.label}
                <Badge>Soon</Badge>
              </span>
            ),
          )}
        </nav>
        <p className="text-xs text-slate-400">Demo with synthetic data only.</p>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex items-center justify-between border-b border-slate-200 bg-white px-6 py-3">
          <div className="md:hidden">
            <Logo />
          </div>
          <div className="hidden md:block">
            <ApiStatus />
          </div>
          <div className="flex items-center gap-4">
            <div className="text-right leading-tight">
              <p className="text-sm font-medium text-slate-900">{user.name}</p>
              <p className="text-xs text-slate-500">
                {ROLE_LABEL[user.role]}
                {context ? ` · ${context}` : ""}
              </p>
            </div>
            <button
              onClick={() => {
                logout();
                router.replace("/login");
              }}
              className="rounded-lg px-3 py-1.5 text-sm text-slate-600 ring-1 ring-slate-300 hover:bg-slate-50"
            >
              Sign out
            </button>
          </div>
        </header>
        <main className="mx-auto w-full max-w-6xl flex-1 p-6 md:p-8">{children}</main>
      </div>
    </div>
  );
}
