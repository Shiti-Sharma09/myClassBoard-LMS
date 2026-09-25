import type { Role } from "@/lib/types";

export interface NavItem {
  label: string;
  href: string;
  description: string;
  /** false until the module ships. The item shows as "Soon" and is not clickable. */
  ready: boolean;
}

/** One place that says what each role can reach. Flip `ready` as each module lands. */
export const NAV: Record<Role, NavItem[]> = {
  teacher: [
    { label: "Notes & OCR", href: "/teacher/notes", description: "Digitise handwritten notes and keep a notes library.", ready: true },
    { label: "Question Bank", href: "/teacher/questions", description: "Generate questions from notes and export a paper.", ready: true },
    { label: "Parent Summaries", href: "/teacher/summaries", description: "Review and approve AI progress summaries.", ready: false },
    { label: "Interview Reports", href: "/teacher/interviews", description: "See how students did in AI interviews.", ready: false },
  ],
  student: [
    { label: "My Notes", href: "/student/notes", description: "Photograph handwritten notes and turn them into text.", ready: true },
    { label: "Tests", href: "/student/tests", description: "Take tests and see which topics need work.", ready: false },
    { label: "AI Interview", href: "/student/interview", description: "Practise a spoken or typed interview on your notes.", ready: false },
  ],
  parent: [
    { label: "Progress Summary", href: "/parent/summary", description: "A plain-language view of how your child is doing.", ready: false },
  ],
  admin: [
    { label: "Demo Data", href: "/admin/data", description: "Reset the demo school to a fresh state.", ready: false },
    { label: "Settings", href: "/admin/settings", description: "Weak-topic threshold and other options.", ready: false },
  ],
};
