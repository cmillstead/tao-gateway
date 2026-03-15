import { useQuery } from "@tanstack/react-query";
import client from "@/api/client";
import { extractErrorMessage } from "@/api/errors";

const USAGE_QUERY_KEY = "dashboard-usage";

interface UseUsageParams {
  subnet?: string;
  startDate?: string;
  endDate?: string;
  granularity?: "daily" | "monthly";
}

export function useUsage(params: UseUsageParams = {}) {
  const { subnet, startDate, endDate, granularity = "daily" } = params;

  return useQuery({
    queryKey: [
      USAGE_QUERY_KEY,
      subnet,
      startDate,
      endDate,
      granularity,
    ],
    queryFn: async () => {
      const { data, error } = await client.GET("/dashboard/usage", {
        params: {
          query: {
            subnet: subnet ?? undefined,
            start_date: startDate ?? undefined,
            end_date: endDate ?? undefined,
            granularity,
          },
        },
      });
      if (error) {
        throw new Error(
          extractErrorMessage(error, "Failed to load usage data"),
        );
      }
      return data;
    },
    staleTime: 60_000,
    refetchInterval: 300_000,
  });
}
