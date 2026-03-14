import { useQuery } from "@tanstack/react-query";
import { fetchJson } from "@/lib/api";
import type { OverviewData } from "@/types";

const OVERVIEW_QUERY_KEY = ["dashboard-overview"];

export function useOverview() {
  return useQuery({
    queryKey: OVERVIEW_QUERY_KEY,
    queryFn: () => fetchJson<OverviewData>("/dashboard/overview"),
  });
}
