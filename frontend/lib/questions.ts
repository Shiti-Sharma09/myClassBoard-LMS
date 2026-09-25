export type QuestionType = "mcq" | "short" | "long" | "fill_blank" | "true_false";

export const TYPE_LABEL: Record<QuestionType, string> = {
  mcq: "Multiple choice",
  short: "Short answer",
  long: "Long answer",
  fill_blank: "Fill in the blank",
  true_false: "True / False",
};

export const TYPES = Object.keys(TYPE_LABEL) as QuestionType[];
export const DIFFICULTIES = ["easy", "medium", "hard"] as const;
export const BLOOMS = ["Remember", "Understand", "Apply", "Analyze", "Evaluate", "Create"] as const;

export const VERSION_HINT: Record<number, string> = {
  1: "Balanced mix",
  2: "Application and thinking",
  3: "Recall and understanding",
};

export interface Question {
  id: number;
  set_id: number;
  note_id: number;
  position: number;
  type: QuestionType;
  text: string;
  options: string[] | null;
  answer: string;
  explanation: string;
  difficulty: string;
  bloom: string;
  topic: string;
  marks: number;
  status: "draft" | "accepted" | "discarded";
  edited: boolean;
}

export interface QuestionSet {
  id: number;
  note_id: number;
  version: number;
  emphasis: string;
  requested_count: number;
  types: string[];
  difficulty: string;
  shortfall_message: string | null;
  generation_seconds: number | null;
  created_at: string;
  questions: Question[];
}

export interface NoteTopic {
  index: number;
  title: string;
  words: number;
  recap: boolean;
}

export interface BankItem extends Question {
  note_title: string;
  chapter_id: number | null;
  chapter_title: string | null;
}

export interface BankTopic {
  topic: string;
  count: number;
}
export interface BankChapter {
  chapter_id: number | null;
  chapter_title: string;
  count: number;
  topics: BankTopic[];
}
export interface BankSubject {
  subject: string;
  count: number;
  chapters: BankChapter[];
}

export interface BankStats {
  accepted: number;
  discarded: number;
  pending: number;
  edited: number;
  usable_rate: number | null;
}

/** Fields the teacher can change on a question. */
export type QuestionPatch = Partial<Pick<Question, "text" | "options" | "answer" | "explanation" | "difficulty" | "bloom" | "topic" | "marks" | "status">>;

export function difficultyTone(d: string): "green" | "amber" | "red" | "slate" {
  return d === "easy" ? "green" : d === "medium" ? "amber" : d === "hard" ? "red" : "slate";
}
