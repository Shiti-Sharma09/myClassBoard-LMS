export interface TestRow {
  id: number;
  title: string;
  question_count: number;
  total_marks: number;
  created_at: string;
  status: "todo" | "done";
  marks: number | null;
  percent: number | null;
}

export interface PaperQuestion {
  id: number;
  type: "mcq" | "short" | "long" | "fill_blank" | "true_false";
  text: string;
  options: string[] | null;
  marks: number;
}

export interface TestPaper {
  id: number;
  title: string;
  total_marks: number;
  submitted: boolean;
  questions: PaperQuestion[];
}

export interface TopicScore {
  topic: string;
  marks: number;
  max_marks: number;
  percent: number;
  weak: boolean;
  questions: number;
  missed: Array<{ question_id: number; text: string }>;
  note_id: number | null;
  note_title: string | null;
}

export interface ReviewedQuestion {
  question_id: number;
  position: number;
  type: PaperQuestion["type"];
  text: string;
  options: string[] | null;
  topic: string;
  your_answer: string;
  correct_answer: string;
  explanation: string;
  marks_awarded: number;
  max_marks: number;
  feedback: string | null;
  scored_by: "code" | "ai" | "keyword";
}

export interface Report {
  assessment_id: number;
  title: string;
  submitted_at: string;
  marks: number;
  max_marks: number;
  percent: number;
  weak_threshold: number;
  ai_fallback: boolean;
  topics: TopicScore[];
  priorities: TopicScore[];
  questions: ReviewedQuestion[];
}

export interface Results {
  assessment_id: number;
  title: string;
  class_name: string;
  max_marks: number;
  submitted_count: number;
  student_count: number;
  students: Array<{ student_id: number; name: string; submitted: boolean; marks: number | null; percent: number | null }>;
  class_topics: Array<{ topic: string; percent: number; weak: boolean }>;
}
