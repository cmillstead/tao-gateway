import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { formatRelativeTime } from "@/lib/format";
import { SUBNET_DISPLAY_NAMES } from "@/components/usage/subnet-constants";
import type { SubnetMetagraphStatus } from "@/types/admin";

interface MetagraphStatusCardProps {
  subnet: SubnetMetagraphStatus;
}

function getSyncStatusDisplay(status: SubnetMetagraphStatus) {
  if (status.sync_status === "never_synced") {
    return { label: "Never Synced", className: "bg-gray-100 text-gray-800" };
  }
  if (status.is_stale) {
    return { label: "Stale", className: "bg-red-100 text-red-800" };
  }
  if (status.sync_status === "degraded") {
    return { label: "Degraded", className: "bg-amber-100 text-amber-800" };
  }
  return { label: "Healthy", className: "bg-green-100 text-green-800" };
}

export function MetagraphStatusCard({ subnet }: MetagraphStatusCardProps) {
  const status = getSyncStatusDisplay(subnet);

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
            <p className="text-xs text-muted-foreground">Last Sync</p>
            <p className="text-sm font-medium text-foreground">
              {formatRelativeTime(subnet.last_sync_time)}
            </p>
          </div>
          <div>
            <p className="text-xs text-muted-foreground">Staleness</p>
            <p className="text-sm font-medium text-foreground">
              {Math.floor(subnet.staleness_seconds)}s
            </p>
          </div>
          <div>
            <p className="text-xs text-muted-foreground">Failures</p>
            <p className="text-sm font-medium text-foreground">
              {subnet.consecutive_failures}
            </p>
          </div>
          <div>
            <p className="text-xs text-muted-foreground">Active Miners</p>
            <p className="text-sm font-medium text-foreground">
              {subnet.active_miners}
            </p>
          </div>
        </div>
        {subnet.is_stale && (
          <p className="mt-3 text-xs text-red-700 dark:text-red-400">
            Stale — last synced {formatRelativeTime(subnet.last_sync_time)}
          </p>
        )}
        {subnet.last_sync_error && (
          <p className="mt-2 text-xs text-red-600">
            Error: {subnet.last_sync_error}
          </p>
        )}
      </CardContent>
    </Card>
  );
}
