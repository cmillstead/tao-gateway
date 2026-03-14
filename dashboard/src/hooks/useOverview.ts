import { useQuery } from "@tanstack/react-query";
import client from "@/api/client";
import { extractErrorMessage } from "@/api/errors";

const OVERVIEW_QUERY_KEY = ["dashboard-overview"];

export function useOverview() {
  return useQuery({
    queryKey: OVERVIEW_QUERY_KEY,
    queryFn: async () => {
      const { data, error } = await client.GET("/dashboard/overview");
      if (error) {
        throw new Error(extractErrorMessage(error, "Failed to load overview"));
      }
      return data;
    },
  });
}
