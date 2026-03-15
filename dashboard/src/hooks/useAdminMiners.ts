import { useQuery } from "@tanstack/react-query";
import { adminFetch } from "@/api/adminFetch";
import type { MinerResponse } from "@/types/admin";

export function useAdminMiners() {
  return useQuery({
    queryKey: ["admin-miners"],
    queryFn: () => adminFetch<MinerResponse>("/admin/miners"),
    staleTime: 30_000,
    refetchInterval: 60_000,
  });
}
