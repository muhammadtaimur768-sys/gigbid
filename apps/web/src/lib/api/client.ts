import createClient from "openapi-fetch";
import type { paths } from "./schema";

const TOKEN_KEY = "gigbid.token";

export function getToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function setToken(token: string | null) {
  try {
    if (token) localStorage.setItem(TOKEN_KEY, token);
    else localStorage.removeItem(TOKEN_KEY);
  } catch {
    /* storage unavailable: cookie session still works */
  }
}

/** Typed client generated from FastAPI's OpenAPI schema. */
export const client = createClient<paths>({ baseUrl: "", credentials: "include" });

client.use({
  onRequest({ request }) {
    const token = getToken();
    if (token && !request.headers.has("Authorization")) {
      request.headers.set("Authorization", `Bearer ${token}`);
    }
    if (!request.headers.has("X-Trace-Id")) {
      request.headers.set("X-Trace-Id", newTraceId());
    }
    return request;
  },
});

export function newTraceId(): string {
  const c = globalThis.crypto;
  if (c && "randomUUID" in c) return c.randomUUID().replace(/-/g, "");
  return Math.random().toString(16).slice(2) + Date.now().toString(16);
}

export class ApiError extends Error {
  status: number;
  detail: unknown;
  constructor(status: number, message: string, detail?: unknown) {
    super(message);
    this.status = status;
    this.detail = detail;
  }
}

type Method = "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
export type ApiPath = Extract<keyof paths, string>;

interface CallOpts {
  path?: Record<string, string | number>;
  query?: Record<string, unknown>;
  body?: unknown;
  formData?: FormData;
}

function errorMessage(status: number, detail: unknown): string {
  if (detail && typeof detail === "object" && "detail" in detail) {
    const d = (detail as { detail: unknown }).detail;
    if (typeof d === "string") return d;
    if (Array.isArray(d) && d[0] && typeof d[0] === "object" && "msg" in d[0]) return String(d[0].msg);
  }
  if (status === 401) return "Please sign in again.";
  if (status === 402) return "Not enough Connects for this proposal.";
  if (status === 429) return "Rate limited by the marketplace. Try again shortly.";
  if (status === 503) return "Marketplace unavailable. GigBid is running in degraded mode.";
  return `Request failed (${status})`;
}

/**
 * Single choke point for API calls. The path parameter is checked against the
 * generated `paths` type, so a renamed or removed route fails `tsc`.
 */
export async function call<T>(method: Method, path: ApiPath, opts: CallOpts = {}): Promise<T> {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const c = client as any;
  const init: Record<string, unknown> = { params: { path: opts.path, query: opts.query } };
  if (opts.formData) {
    init.body = opts.formData;
    init.bodySerializer = (b: FormData) => b;
  } else if (opts.body !== undefined) {
    init.body = opts.body;
  }
  let res: { data?: unknown; error?: unknown; response: Response };
  try {
    res = await c[method](path, init);
  } catch (e) {
    throw new ApiError(0, "Network error: the GigBid API is unreachable.", e);
  }
  if (!res.response.ok) {
    throw new ApiError(res.response.status, errorMessage(res.response.status, res.error), res.error);
  }
  return res.data as T;
}

/** Accepts `[...]`, `{items: [...]}`, `{jobs: [...]}` etc. */
export function asList<T>(data: unknown, ...keys: string[]): T[] {
  if (Array.isArray(data)) return data as T[];
  if (data && typeof data === "object") {
    for (const k of [...keys, "items", "results", "data"]) {
      const v = (data as Record<string, unknown>)[k];
      if (Array.isArray(v)) return v as T[];
    }
  }
  return [];
}
