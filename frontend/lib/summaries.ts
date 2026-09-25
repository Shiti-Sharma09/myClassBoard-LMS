export interface Narrative {
  overall: string;
  strengths: string[];
  areas_to_work_on: string[];
  trend: string;
  home_tips: string[];
}

export interface Facts {
  tests_count: number;
  overall_percent: number;
  weak_threshold: number;
  trend: "improving" | "steady" | "declining" | "not_enough_data";
  trend_from: number | null;
  trend_to: number | null;
  tests: Array<{ name: string; date: string; percent: number }>;
  chapters: Array<{ chapter: string; percent: number }>;
  topics: Array<{ topic: string; chapter: string; percent: number }>;
  strongest: Array<{ topic: string; percent: number }>;
  weak_topics: Array<{ topic: string; chapter: string; percent: number }>;
}

export type SummaryStatus = "none" | "draft" | "approved";

export interface SummaryRow {
  student_id: number;
  name: string;
  class_name: string;
  status: SummaryStatus;
  source: "ai" | "template" | null;
  edited: boolean;
  overall_percent: number | null;
  trend: Facts["trend"] | null;
  weak_topic_count: number | null;
}

export interface SummaryDetail {
  student_id: number;
  name: string;
  class_name: string;
  status: SummaryStatus;
  source: "ai" | "template" | null;
  edited: boolean;
  verify_failures: number;
  narrative: Narrative | null;
  facts: Facts | null;
  generated_at: string | null;
  approved_at: string | null;
}

export interface ChildSummary {
  available: boolean;
  child_name: string;
  narrative: Narrative | null;
  facts: Facts | null;
  approved_at: string | null;
}

export const TREND_LABEL: Record<Facts["trend"], string> = {
  improving: "Improving",
  steady: "Steady",
  declining: "Needs attention",
  not_enough_data: "Not enough tests",
};
