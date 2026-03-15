import { useQuery } from "@tanstack/react-query";
import { adminFetch } from "@/api/adminFetch";
import type { DeveloperMetrics } from "@/types/admin";

export function useAdminDevelopers() {
  return useQuery({
    queryKey: ["admin-developers"],
    queryFn: () => adminFetch<DeveloperMetrics>("/admin/developers"),
    staleTime: 60_000,
    refetchInterval: 120_000,
  });
}
