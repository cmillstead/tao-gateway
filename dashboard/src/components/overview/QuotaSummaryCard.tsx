import { Link } from "react-router-dom";
import { Card, CardHeader, CardTitle, CardContent, CardFooter } from "@/components/ui/card";
import { QuotaBar } from "@/components/usage/QuotaBar";
import { useUsage } from "@/hooks/useUsage";

// Fetches usage data independently from the Overview page's useOverview hook.
// TanStack Query deduplicates identical requests within staleTime (60s),
// so navigating to the Usage page reuses the cached response.
export function QuotaSummaryCard() {
  const { data, isLoading, error } = useUsage({
    granularity: "daily",
  });

  if (isLoading) {
    return (
      <div className="h-48 animate-pulse rounded-sm border border-border bg-elevated" />
    );
  }

  if (error) return null;

  const subnetsWithQuota =
    data?.subnets?.filter((s) => s.quota != null) ?? [];

  if (subnetsWithQuota.length === 0) return null;

  return (
    <Card>
      <CardHeader>
        <CardTitle>Quota Usage</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="space-y-4">
          {subnetsWithQuota.map((subnet) => (
            <QuotaBar
              key={subnet.subnet_name}
              subnetName={subnet.subnet_name}
              monthlyLimit={subnet.quota!.monthly_limit}
              monthlyUsed={subnet.quota!.monthly_used}
            />
          ))}
        </div>
      </CardContent>
      <CardFooter>
        <Link
          to="/dashboard/usage"
          className="text-sm font-medium text-indigo-600 hover:text-indigo-500"
        >
          View details
        </Link>
      </CardFooter>
    </Card>
  );
}
