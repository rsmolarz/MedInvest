export type ApiError = { error: string; detail?: string };

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "";

function getCsrfOrSessionHeaders(): HeadersInit {
  // This scaffold assumes cookie-based auth (Flask session). If you switch to tokens,
  // update here.
  return {
    "Content-Type": "application/json",
  };
}

export async function apiGet<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "GET",
    credentials: "include",
    headers: getCsrfOrSessionHeaders(),
    cache: "no-store",
  });
  if (!res.ok) {
    const data = (await res.json().catch(() => ({}))) as ApiError;
    throw new Error(data.detail || data.error || `HTTP ${res.status}`);
  }
  return (await res.json()) as T;
}

export async function apiPost<T>(path: string, body: unknown, opts?: { idempotencyKey?: string }): Promise<T> {
  const headers: Record<string, string> = { ...(getCsrfOrSessionHeaders() as any) };
  if (opts?.idempotencyKey) headers["Idempotency-Key"] = opts.idempotencyKey;

  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    credentials: "include",
    headers,
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const data = (await res.json().catch(() => ({}))) as ApiError;
    throw new Error(data.detail || data.error || `HTTP ${res.status}`);
  }
  return (await res.json()) as T;
}
