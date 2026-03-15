import { useState } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { useAdminMetrics } from "@/hooks/useAdminMetrics";
import { SubnetHealthCard } from "@/components/admin/SubnetHealthCard";
import { cn } from "@/lib/utils";

type TimeRange = "1h" | "24h" | "7d" | "30d";

const TIME_RANGE_OPTIONS: { value: TimeRange; label: string }[] = [
  { value: "1h", label: "1 hour" },
  { value: "24h", label: "24 hours" },
  { value: "7d", label: "7 days" },
  { value: "30d", label: "30 days" },
];

export function Admin() {
  const [timeRange, setTimeRange] = useState<TimeRange>("24h");
  const { data, isLoading, error } = useAdminMetrics(timeRange);

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-foreground">System Health</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Monitor gateway performance across all subnets
          </p>
        </div>
        <div
          role="group"
          aria-label="Time range"
          className="inline-flex items-center gap-1 rounded-md bg-elevated p-1"
        >
          {TIME_RANGE_OPTIONS.map((opt) => (
            <button
              key={opt.value}
              type="button"
              onClick={() => setTimeRange(opt.value)}
              aria-pressed={timeRange === opt.value}
              className={cn(
                "rounded-sm px-3 py-1.5 text-sm font-medium transition-colors",
                "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2",
                timeRange === opt.value
                  ? "bg-background text-foreground shadow-sm"
                  : "text-muted-foreground hover:text-foreground",
              )}
            >
              {opt.label}
            </button>
          ))}
        </div>
      </div>

      {error && (
        <div className="mb-4 rounded-md border border-destructive/30 bg-destructive/10 p-4" role="alert">
          <p className="text-sm text-destructive">
            Failed to load metrics: {error.message}
          </p>
        </div>
      )}

      {isLoading && (
        <div className="space-y-4">
          <div className="grid grid-cols-3 gap-4">
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-20 animate-pulse rounded-sm border border-border bg-elevated" />
            ))}
          </div>
          <div className="h-40 animate-pulse rounded-sm border border-border bg-elevated" />
        </div>
      )}

      {data && (
        <div className="space-y-6">
          {/* Summary row */}
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            <Card>
              <CardContent className="pt-6">
                <p className="text-xs text-muted-foreground">Total Requests</p>
                <p className="text-2xl font-bold text-foreground">
                  {data.total_requests.toLocaleString()}
                </p>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <p className="text-xs text-muted-foreground">Overall Error Rate</p>
                <p className="text-2xl font-bold text-foreground">
                  {(data.overall_error_rate * 100).toFixed(1)}%
                </p>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <p className="text-xs text-muted-foreground">Active Subnets</p>
                <p className="text-2xl font-bold text-foreground">
                  {data.subnets.length}
                </p>
              </CardContent>
            </Card>
          </div>

          {/* Per-subnet health cards */}
          <div className="space-y-4">
            {data.subnets.map((subnet) => (
              <SubnetHealthCard key={subnet.netuid} subnet={subnet} />
            ))}
          </div>

          {data.subnets.length === 0 && (
            <div className="py-8 text-center">
              <p className="text-sm text-muted-foreground">
                No subnet data available for this time range.
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
