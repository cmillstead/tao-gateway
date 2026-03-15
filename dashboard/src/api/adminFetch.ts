/**
 * Fetch helper for admin endpoints that are not in the OpenAPI schema.
 * Uses native fetch() with credentials: "include" for cookie auth.
 */
export async function adminFetch<T>(path: string): Promise<T> {
  const response = await fetch(path, { credentials: "include" });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    const message =
      body?.error?.message ?? body?.detail ?? `Request failed: ${response.status}`;
    throw new Error(message);
  }
  return response.json() as Promise<T>;
}
