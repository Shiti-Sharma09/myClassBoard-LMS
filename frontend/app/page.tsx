"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { PageLoading } from "@/components/ui";
import { homeFor, useAuth } from "@/lib/auth";

/** The front door: send people to their own area, or to the login page. */
export default function Home() {
  const { user, loading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (loading) return;
    router.replace(user ? homeFor(user.role) : "/login");
  }, [loading, user, router]);

  return <PageLoading />;
}
