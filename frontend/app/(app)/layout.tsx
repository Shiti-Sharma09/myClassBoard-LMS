import type { ReactNode } from "react";
import { AppShell } from "@/components/AppShell";

/** Everything inside (app) needs a signed-in user. AppShell handles the redirect. */
export default function SignedInLayout({ children }: { children: ReactNode }) {
  return <AppShell>{children}</AppShell>;
}
