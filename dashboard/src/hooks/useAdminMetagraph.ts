import { useQuery } from "@tanstack/react-query";
import { adminFetch } from "@/api/adminFetch";
import type { MetagraphResponse } from "@/types/admin";

export function useAdminMetagraph() {
  return useQuery({
    queryKey: ["admin-metagraph"],
    queryFn: () => adminFetch<MetagraphResponse>("/admin/metagraph"),
    staleTime: 10_000,
    refetchInterval: 30_000,
  });
}
