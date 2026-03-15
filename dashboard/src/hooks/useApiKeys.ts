import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import client from "@/api/client";
import { extractErrorMessage } from "@/api/errors";
import type { ApiKeyCreateRequest } from "@/types";

const API_KEYS_QUERY_KEY = ["api-keys"];

export function useApiKeys(params?: { limit?: number; offset?: number; includeRevoked?: boolean }) {
  const limit = params?.limit ?? 50;
  const offset = params?.offset ?? 0;
  const includeRevoked = params?.includeRevoked ?? true;

  return useQuery({
    queryKey: [...API_KEYS_QUERY_KEY, { limit, offset, includeRevoked }],
    queryFn: async () => {
      const { data, error } = await client.GET("/dashboard/api-keys", {
        params: {
          query: { limit, offset, include_revoked: includeRevoked },
        },
      });
      if (error) {
        throw new Error(extractErrorMessage(error, "Failed to load API keys"));
      }
      return data;
    },
  });
}

export function useCreateApiKey() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (req: ApiKeyCreateRequest) => {
      const { data, error } = await client.POST("/dashboard/api-keys", {
        body: req,
      });
      if (error) {
        throw new Error(extractErrorMessage(error, "Failed to create API key"));
      }
      return data;
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: API_KEYS_QUERY_KEY });
    },
  });
}

export function useRotateApiKey() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (keyId: string) => {
      const { data, error } = await client.POST("/dashboard/api-keys/rotate/{key_id}", {
        params: { path: { key_id: keyId } },
      });
      if (error) {
        throw new Error(extractErrorMessage(error, "Failed to rotate API key"));
      }
      return data;
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: API_KEYS_QUERY_KEY });
    },
  });
}

export function useRevokeApiKey() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (keyId: string) => {
      const { data, error } = await client.DELETE("/dashboard/api-keys/{key_id}", {
        params: { path: { key_id: keyId } },
      });
      if (error) {
        throw new Error(extractErrorMessage(error, "Failed to revoke API key"));
      }
      return data;
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: API_KEYS_QUERY_KEY });
    },
  });
}

export function useUpdateApiKey() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({ keyId, debugMode }: { keyId: string; debugMode: boolean }) => {
      const { data, error } = await client.PATCH("/dashboard/api-keys/{key_id}", {
        params: { path: { key_id: keyId } },
        body: { debug_mode: debugMode },
      });
      if (error) {
        throw new Error(extractErrorMessage(error, "Failed to update API key"));
      }
      return data;
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: API_KEYS_QUERY_KEY });
    },
  });
}
