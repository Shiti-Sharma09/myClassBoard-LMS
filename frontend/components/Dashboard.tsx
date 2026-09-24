"use client";

import Link from "next/link";
import { useAuth } from "@/lib/auth";
import { NAV } from "@/lib/nav";
import { Badge, Card } from "@/components/ui";

const INTRO = {
  teacher: "Turn notes into questions, digitise handwriting, and keep parents informed, with far less manual work.",
  student: "Digitise your notes, test yourself, and practise with an AI interviewer.",
  parent: "A clear, friendly picture of how your child is doing at school.",
  admin: "Manage the demo school and its settings.",
} as const;

/** Shared landing page for every role. It lists what the role can do and what is ready yet. */
export function Dashboard() {
  const { user } = useAuth();
  if (!user) return null;
  const items = NAV[user.role];

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900">Welcome, {user.name.split(" ")[0]}</h1>
        <p className="mt-1 max-w-2xl text-slate-600">{INTRO[user.role]}</p>
      </div>

      {user.role === "parent" && user.child && (
        <Card>
          <p className="text-sm text-slate-500">Your child</p>
          <p className="text-lg font-semibold text-slate-900">{user.child.name}</p>
          <p className="text-sm text-slate-600">Class {user.child.class_name}</p>
        </Card>
      )}

      <section aria-label="Modules" className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {items.map((item) => {
          const body = (
            <Card className={item.ready ? "h-full transition hover:border-indigo-300 hover:shadow" : "h-full opacity-70"}>
              <div className="flex items-start justify-between gap-3">
                <h2 className="font-semibold text-slate-900">{item.label}</h2>
                {!item.ready && <Badge>Coming soon</Badge>}
              </div>
              <p className="mt-2 text-sm text-slate-600">{item.description}</p>
            </Card>
          );
          return item.ready ? (
            <Link key={item.href} href={item.href}>
              {body}
            </Link>
          ) : (
            <div key={item.href}>{body}</div>
          );
        })}
      </section>
    </div>
  );
}
