import { useQuery } from "@tanstack/react-query";
import { adminFetch } from "@/api/adminFetch";
import type { MetricsResponse } from "@/types/admin";

export function useAdminMetrics(timeRange: string = "24h") {
  return useQuery({
    queryKey: ["admin-metrics", timeRange],
    queryFn: () =>
      adminFetch<MetricsResponse>(
        `/admin/metrics?time_range=${encodeURIComponent(timeRange)}`,
      ),
    staleTime: 30_000,
    refetchInterval: 60_000,
  });
}
