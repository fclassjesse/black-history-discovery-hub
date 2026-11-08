export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function handle<T>(res: Response): Promise<T> {
  if (res.ok) return (await res.json()) as T;
  let message = `${res.status} ${res.statusText}`;
  try {
    const body = await res.json();
    if (typeof body?.detail === "string") message = body.detail;
    else if (Array.isArray(body?.detail)) message = body.detail.map((d: { msg?: string }) => d.msg ?? JSON.stringify(d)).join("; ");
  } catch {
    /* non-JSON error body */
  }
  throw new ApiError(res.status, message);
}

export async function apiGet<T>(path: string, init?: RequestInit): Promise<T> {
  return handle<T>(await fetch(path, { credentials: "include", cache: "no-store", ...init }));
}

/** In-flight requests by key. A second caller for the same request (React dev double-effects, or a prefetch made at
 *  ask time) shares the first one's promise instead of sending another request. Entries leave once settled. */
const inflight = new Map<string, Promise<unknown>>();

function shared<T>(key: string, run: () => Promise<T>): Promise<T> {
  const existing = inflight.get(key);
  if (existing) return existing as Promise<T>;
  const p = run().finally(() => inflight.delete(key));
  inflight.set(key, p);
  return p;
}

/** GET that joins an identical request already in flight. */
export function apiGetShared<T>(path: string): Promise<T> {
  return shared(`GET ${path}`, () => apiGet<T>(path));
}

/** POST that joins an identical request (same path and body) already in flight. */
export function apiPostShared<T>(path: string, body: unknown): Promise<T> {
  return shared(`POST ${path} ${JSON.stringify(body)}`, () => apiJson<T>(path, "POST", body));
}

export async function apiJson<T>(path: string, method: "POST" | "PUT" | "PATCH" | "DELETE", body?: unknown): Promise<T> {
  return handle<T>(
    await fetch(path, { method, credentials: "include", headers: { "Content-Type": "application/json" }, body: body === undefined ? undefined : JSON.stringify(body) }),
  );
}

export async function apiForm<T>(path: string, form: FormData, method: "POST" | "PUT" = "POST"): Promise<T> {
  return handle<T>(await fetch(path, { method, credentials: "include", body: form }));
}

export function qs(params: Record<string, string | number | boolean | undefined | null>): string {
  const sp = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v === undefined || v === null || v === "" || v === false) continue;
    sp.set(k, String(v));
  }
  const s = sp.toString();
  return s ? `?${s}` : "";
}
