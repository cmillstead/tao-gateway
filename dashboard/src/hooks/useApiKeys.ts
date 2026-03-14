import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import type {
  ApiKeyCreateRequest,
  ApiKeyCreateResponse,
  ApiKeyListResponse,
  ApiKeyRotateResponse,
} from "@/types";

const API_KEYS_QUERY_KEY = ["api-keys"];

async function fetchJson<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, { ...init, credentials: "include" });
  if (!res.ok) {
    const body = await res.json().catch(() => ({ error: { message: "Request failed" } }));
    throw new Error(body?.error?.message ?? `HTTP ${res.status}`);
  }
  return res.json() as Promise<T>;
}

export function useApiKeys(params?: { limit?: number; offset?: number; includeRevoked?: boolean }) {
  const limit = params?.limit ?? 50;
  const offset = params?.offset ?? 0;
  const includeRevoked = params?.includeRevoked ?? true;

  return useQuery({
    queryKey: [...API_KEYS_QUERY_KEY, { limit, offset, includeRevoked }],
    queryFn: () =>
      fetchJson<ApiKeyListResponse>(
        `/dashboard/api-keys?limit=${limit}&offset=${offset}&include_revoked=${includeRevoked}`,
      ),
  });
}

export function useCreateApiKey() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (req: ApiKeyCreateRequest) =>
      fetchJson<ApiKeyCreateResponse>("/dashboard/api-keys", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(req),
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: API_KEYS_QUERY_KEY });
    },
  });
}

export function useRotateApiKey() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (keyId: string) =>
      fetchJson<ApiKeyRotateResponse>(`/dashboard/api-keys/rotate/${keyId}`, {
        method: "POST",
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: API_KEYS_QUERY_KEY });
    },
  });
}

export function useRevokeApiKey() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (keyId: string) =>
      fetchJson<{ message: string }>(`/dashboard/api-keys/${keyId}`, {
        method: "DELETE",
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: API_KEYS_QUERY_KEY });
    },
  });
}
