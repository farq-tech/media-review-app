/**
 * API client for POI Review Dashboard.
 * All API calls go through Next.js rewrites → poi-api-eu.onrender.com
 */

export type ApiFetchOptions = RequestInit & {
  params?: Record<string, string>;
};

export async function apiFetch<T = unknown>(
  path: string,
  options: ApiFetchOptions = {}
): Promise<T> {
  const { params, ...init } = options;

  // Build URL - use relative path (Next.js rewrites handle the proxy)
  const url = new URL(path, typeof window !== "undefined" ? window.location.origin : "http://localhost:3000");
  if (params) {
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== "") url.searchParams.set(k, v);
    });
  }

  const headers = new Headers(init.headers);
  if (!headers.has("Content-Type") && init.body && typeof init.body === "string") {
    headers.set("Content-Type", "application/json");
  }

  const res = await fetch(url.toString(), { ...init, headers });

  if (!res.ok) {
    const text = await res.text();
    let message = text;
    try {
      const j = JSON.parse(text) as { message?: string; error?: string };
      message = j.message ?? j.error ?? text;
    } catch {
      // use text as-is
    }
    throw new Error(message || `HTTP ${res.status}`);
  }

  const contentType = res.headers.get("Content-Type") ?? "";
  if (contentType.includes("application/json")) return res.json() as Promise<T>;
  return res.text() as unknown as T;
}
