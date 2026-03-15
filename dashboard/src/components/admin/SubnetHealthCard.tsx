import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { SUBNET_DISPLAY_NAMES } from "@/components/usage/subnet-constants";
import type { SubnetMetrics } from "@/types/admin";

interface SubnetHealthCardProps {
  subnet: SubnetMetrics;
}

function getHealthStatus(errorRate: number) {
  if (errorRate < 0.02) return { label: "Healthy", className: "bg-green-100 text-green-800" };
  if (errorRate < 0.1) return { label: "Degraded", className: "bg-amber-100 text-amber-800" };
  return { label: "Critical", className: "bg-red-100 text-red-800" };
}

export function SubnetHealthCard({ subnet }: SubnetHealthCardProps) {
  const status = getHealthStatus(subnet.error_rate);

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between pb-2">
        <CardTitle className="text-base font-medium">
          {SUBNET_DISPLAY_NAMES[subnet.subnet_name] ?? subnet.subnet_name}
          <span className="ml-2 text-xs text-muted-foreground">
            (SN{subnet.netuid})
          </span>
        </CardTitle>
        <Badge className={cn(status.className)}>{status.label}</Badge>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
          <div>
            <p className="text-xs text-muted-foreground">Requests</p>
            <p className="text-lg font-semibold text-foreground">
              {subnet.request_count.toLocaleString()}
            </p>
          </div>
          <div>
            <p className="text-xs text-muted-foreground">Error Rate</p>
            <p className="text-lg font-semibold text-foreground">
              {(subnet.error_rate * 100).toFixed(1)}%
            </p>
          </div>
          <div>
            <p className="text-xs text-muted-foreground">p50 Latency</p>
            <p className="text-lg font-semibold text-foreground">
              {subnet.p50_latency_ms}ms
            </p>
          </div>
          <div>
            <p className="text-xs text-muted-foreground">p95 Latency</p>
            <p className="text-lg font-semibold text-foreground">
              {subnet.p95_latency_ms}ms
            </p>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
