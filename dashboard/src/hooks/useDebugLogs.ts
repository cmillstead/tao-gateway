import { useQuery } from "@tanstack/react-query";
import client from "@/api/client";
import { extractErrorMessage } from "@/api/errors";

const DEBUG_LOGS_QUERY_KEY = ["debug-logs"];

export function useDebugLogs(keyId: string | null, params?: { limit?: number; offset?: number }) {
  const limit = params?.limit ?? 20;
  const offset = params?.offset ?? 0;

  return useQuery({
    queryKey: [...DEBUG_LOGS_QUERY_KEY, keyId, { limit, offset }],
    queryFn: async () => {
      if (!keyId) return { items: [], total: 0 };
      const { data, error } = await client.GET("/dashboard/api-keys/{key_id}/debug-logs", {
        params: {
          path: { key_id: keyId },
          query: { limit, offset },
        },
      });
      if (error) {
        throw new Error(extractErrorMessage(error, "Failed to load debug logs"));
      }
      return data;
    },
    enabled: !!keyId,
    staleTime: 30_000,
    refetchInterval: 60_000,
  });
}
