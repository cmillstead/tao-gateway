import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import type { SubnetOverview } from "@/types";

interface RateLimitsCardProps {
  subnets: SubnetOverview[];
}

export function RateLimitsCard({ subnets }: RateLimitsCardProps) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Rate Limits</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="space-y-3">
          {subnets.map((subnet) => (
            <div key={subnet.netuid}>
              <p className="text-sm font-medium text-foreground">
                {subnet.name}
              </p>
              <p className="mt-0.5 text-sm text-muted-foreground">
                {subnet.rate_limits.minute} req/min
                {" · "}
                {subnet.rate_limits.day.toLocaleString()} /day
                {" · "}
                {subnet.rate_limits.month.toLocaleString()} /month
              </p>
            </div>
          ))}
          {subnets.length === 0 && (
            <p className="text-sm text-muted-foreground">No rate limit data available</p>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
