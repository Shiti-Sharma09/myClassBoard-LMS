"use client";

import { Bar, BarChart, CartesianGrid, Cell, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Badge, Card } from "@/components/ui";
import { TREND_LABEL, type Facts, type Narrative } from "@/lib/summaries";

const GOOD = "#4f46e5";
const WEAK = "#f59e0b";

function List({ title, items, empty }: { title: string; items: string[]; empty?: string }) {
  return (
    <div>
      <h3 className="text-sm font-semibold text-slate-700">{title}</h3>
      {items.length > 0 ? (
        <ul className="mt-1 list-disc space-y-1 pl-5 text-sm text-slate-700">
          {items.map((item, i) => (
            <li key={i}>{item}</li>
          ))}
        </ul>
      ) : (
        <p className="mt-1 text-sm text-slate-500">{empty}</p>
      )}
    </div>
  );
}

export function NarrativeCard({ narrative }: { narrative: Narrative }) {
  return (
    <Card className="space-y-4" >
      <p className="text-[15px] leading-7 text-slate-800" data-testid="summary-overall">
        {narrative.overall}
      </p>
      <div className="grid gap-5 sm:grid-cols-2">
        <List title="Doing well" items={narrative.strengths} />
        <List title="Topics to practise" items={narrative.areas_to_work_on} empty="Nothing specific right now. Keep it up!" />
      </div>
      <div>
        <h3 className="text-sm font-semibold text-slate-700">Progress over the tests</h3>
        <p className="mt-1 text-sm text-slate-700">{narrative.trend}</p>
      </div>
      <List title="How you can help at home" items={narrative.home_tips} />
    </Card>
  );
}

/** Charts and the weak-topic list, built only from the computed facts (never from the AI text). */
export function SummaryCharts({ facts }: { facts: Facts }) {
  const chapterData = facts.chapters.map((c) => ({ name: c.chapter, percent: c.percent }));
  const testData = facts.tests.map((t) => ({ name: t.name.split(":")[0].replace("Unit Test", "UT"), full: t.name, percent: t.percent }));
  const tone = facts.trend === "improving" ? "green" : facts.trend === "declining" ? "amber" : "slate";

  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <Card className="space-y-2">
        <div className="flex items-center justify-between gap-2">
          <h3 className="font-semibold text-slate-900">Score by chapter</h3>
          <Badge tone="indigo">Overall {facts.overall_percent}%</Badge>
        </div>
        <div className="h-64" role="img" aria-label="Bar chart of the score in each chapter">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={chapterData} margin={{ left: -20, right: 8 }}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} />
              <XAxis dataKey="name" tick={{ fontSize: 10 }} interval={0} tickFormatter={(v: string) => (v.length > 12 ? v.slice(0, 11) + "…" : v)} />
              <YAxis domain={[0, 100]} tick={{ fontSize: 11 }} />
              <Tooltip formatter={(v) => [`${v}%`, "Score"]} />
              <ReferenceLine y={facts.weak_threshold} stroke="#94a3b8" strokeDasharray="4 4" />
              <Bar dataKey="percent" radius={[4, 4, 0, 0]} isAnimationActive={false}>
                {chapterData.map((c) => (
                  <Cell key={c.name} fill={c.percent < facts.weak_threshold ? WEAK : GOOD} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
        <p className="text-xs text-slate-500">The dashed line is {facts.weak_threshold}%. Bars below it are shown in amber.</p>
      </Card>

      <Card className="space-y-2">
        <div className="flex items-center justify-between gap-2">
          <h3 className="font-semibold text-slate-900">Trend across tests</h3>
          <Badge tone={tone}>{TREND_LABEL[facts.trend]}</Badge>
        </div>
        <div className="h-64" role="img" aria-label="Line chart of the score in each test">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={testData} margin={{ left: -20, right: 12 }}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} />
              <XAxis dataKey="name" tick={{ fontSize: 11 }} interval={0} />
              <YAxis domain={[0, 100]} tick={{ fontSize: 11 }} />
              <Tooltip formatter={(v) => [`${v}%`, "Score"]} labelFormatter={(_, p) => p?.[0]?.payload?.full ?? ""} />
              <ReferenceLine y={facts.weak_threshold} stroke="#94a3b8" strokeDasharray="4 4" />
              <Line type="monotone" dataKey="percent" stroke={GOOD} strokeWidth={2.5} dot={{ r: 4 }} isAnimationActive={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </Card>

      <Card className="space-y-2 lg:col-span-2">
        <h3 className="font-semibold text-slate-900">Topics to practise</h3>
        {facts.weak_topics.length === 0 ? (
          <p className="text-sm text-slate-600">Every topic is at or above {facts.weak_threshold}%. Well done!</p>
        ) : (
          <ul className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3" data-testid="weak-topics">
            {facts.weak_topics.map((t) => (
              <li key={`${t.chapter}-${t.topic}`} className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm">
                <p className="font-medium text-amber-900">{t.topic}</p>
                <p className="text-xs text-amber-800">
                  {t.chapter} · {t.percent}%
                </p>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  );
}
