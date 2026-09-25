"use client";

import { notFound, useParams } from "next/navigation";
import { SummaryReview } from "@/components/summary/SummaryReview";

export default function SummaryReviewPage() {
  const { studentId } = useParams<{ studentId: string }>();
  const id = Number(studentId);
  if (!Number.isInteger(id) || id < 1) notFound();
  return <SummaryReview studentId={id} />;
}
