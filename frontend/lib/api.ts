export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8010";

const TOKEN_KEY = "lms_token";
export const UNAUTHORIZED_EVENT = "lms:unauthorized";

/** localStorage can throw (private windows, blocked storage), so every access is guarded. */
export const tokenStore = {
  get(): string | null {
    try {
      return localStorage.getItem(TOKEN_KEY);
    } catch {
      return null;
    }
  },
  set(token: string) {
    try {
      localStorage.setItem(TOKEN_KEY, token);
    } catch {}
  },
  clear() {
    try {
      localStorage.removeItem(TOKEN_KEY);
    } catch {}
  },
};

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

type Options = Omit<RequestInit, "body"> & { json?: unknown; body?: BodyInit };

async function request(path: string, { json, headers, ...init }: Options = {}): Promise<Response> {
  const finalHeaders = new Headers(headers);
  const token = tokenStore.get();
  if (token) finalHeaders.set("Authorization", `Bearer ${token}`);
  let body = init.body;
  if (json !== undefined) {
    finalHeaders.set("Content-Type", "application/json");
    body = JSON.stringify(json);
  }

  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, { ...init, headers: finalHeaders, body });
  } catch {
    throw new ApiError("Can't reach the server. Check that the app is running and try again.", 0);
  }

  if (!res.ok) {
    if (res.status === 401 && token && typeof window !== "undefined") {
      tokenStore.clear();
      window.dispatchEvent(new Event(UNAUTHORIZED_EVENT));
    }
    throw new ApiError(await readError(res), res.status);
  }
  return res;
}

async function readError(res: Response): Promise<string> {
  try {
    const data = await res.json();
    if (typeof data?.detail === "string") return data.detail;
    if (Array.isArray(data?.detail)) return "Some of the details look wrong. Please check and try again.";
  } catch {}
  return "Something went wrong. Please try again.";
}

/** JSON request. Throws ApiError with a message that is safe to show to the user. */
export async function api<T>(path: string, options?: Options): Promise<T> {
  const res = await request(path, options);
  return (await res.json()) as T;
}

/** File download request (for DOCX exports). Returns the blob and the server-suggested filename. */
export async function apiBlob(path: string, options?: Options): Promise<{ blob: Blob; filename: string }> {
  const res = await request(path, options);
  const disposition = res.headers.get("Content-Disposition") ?? "";
  const match = /filename="?([^";]+)"?/.exec(disposition);
  return { blob: await res.blob(), filename: match?.[1] ?? "download" };
}
