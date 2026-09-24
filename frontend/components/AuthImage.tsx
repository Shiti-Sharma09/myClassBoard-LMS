"use client";

import { useEffect, useState } from "react";
import { apiBlob } from "@/lib/api";
import { Spinner } from "@/components/ui";

/** Shows an image from a protected API path. A normal <img> can't send the login token. */
export function AuthImage({ path, alt, className }: { path: string; alt: string; className?: string }) {
  const [state, setState] = useState<{ path: string; url?: string; failed?: boolean }>({ path: "" });

  useEffect(() => {
    let cancelled = false;
    let objectUrl: string | undefined;
    apiBlob(path)
      .then(({ blob }) => {
        objectUrl = URL.createObjectURL(blob);
        if (!cancelled) setState({ path, url: objectUrl });
      })
      .catch(() => !cancelled && setState({ path, failed: true }));
    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [path]);

  if (state.path !== path) {
    return (
      <div className="flex h-40 items-center justify-center rounded-lg bg-slate-100">
        <Spinner size="sm" />
      </div>
    );
  }
  if (state.failed || !state.url) {
    return <div className="flex h-40 items-center justify-center rounded-lg bg-slate-100 text-sm text-slate-500">Image unavailable</div>;
  }
  // eslint-disable-next-line @next/next/no-img-element
  return <img src={state.url} alt={alt} className={className} />;
}
