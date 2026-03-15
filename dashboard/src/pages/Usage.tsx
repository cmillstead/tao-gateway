import { useState } from "react";
import { Link } from "react-router-dom";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import { useUsage } from "@/hooks/useUsage";
import { QuotaBar } from "@/components/usage/QuotaBar";
import { RequestChart } from "@/components/usage/RequestChart";
import { LatencyChart } from "@/components/usage/LatencyChart";
import { DateRangeSelector } from "@/components/usage/DateRangeSelector";
import { getDateRange, type DateRange } from "@/components/usage/date-range";
import {
  SUBNET_DISPLAY_NAMES,
  SUBNET_RATE_LIMITS,
} from "@/components/usage/subnet-constants";

export function Usage() {
  const [dateRange, setDateRange] = useState<DateRange>("30d");
  const [selectedSubnet, setSelectedSubnet] = useState<string | undefined>();
  const { startDate, endDate } = getDateRange(dateRange);
  const { data, isLoading, error } = useUsage({
    startDate,
    endDate,
    granularity: "daily",
  });

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-foreground">Usage & Quota</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Monitor your API consumption and quota status across subnets
        </p>
      </div>

      {error && (
        <div className="mb-4 rounded-md bg-red-50 p-4" role="alert">
          <p className="text-sm text-red-700">
            Failed to load usage data: {error.message}
          </p>
        </div>
      )}

      {isLoading && (
        <div className="space-y-4">
          <div className="h-40 animate-pulse rounded-sm border border-border bg-elevated" />
          <div className="h-8 w-48 animate-pulse rounded-sm bg-elevated" />
          <div className="h-72 animate-pulse rounded-sm border border-border bg-elevated" />
          <div className="h-64 animate-pulse rounded-sm border border-border bg-elevated" />
        </div>
      )}

      {data && (
        <div className="space-y-6">
          {/* Quota Section */}
          <Card>
            <CardHeader>
              <CardTitle>Quota Status</CardTitle>
            </CardHeader>
            <CardContent>
              {data.subnets && data.subnets.length > 0 ? (
                <div className="space-y-5">
                  {data.subnets.map((subnet) =>
                    subnet.quota ? (
                      <div key={subnet.subnet_name} className="space-y-2">
                        <QuotaBar
                          subnetName={subnet.subnet_name}
                          monthlyLimit={subnet.quota.monthly_limit}
                          monthlyUsed={subnet.quota.monthly_used}
                        />
                        <div className="flex gap-4 text-xs text-muted-foreground">
                          <span>
                            {SUBNET_RATE_LIMITS[subnet.subnet_name]?.minute ?? 10}/min
                          </span>
                          <span>
                            {SUBNET_RATE_LIMITS[subnet.subnet_name]?.day ?? 100}/day
                          </span>
                          <span>
                            {subnet.quota.monthly_limit.toLocaleString()}/month
                          </span>
                        </div>
                      </div>
                    ) : null,
                  )}
                </div>
              ) : (
                <EmptyState />
              )}
            </CardContent>
          </Card>

          {/* Date Range + Charts */}
          {data.subnets && data.subnets.length > 0 && (
            <>
              <DateRangeSelector value={dateRange} onChange={setDateRange} />

              {/* Request Volume Chart */}
              <Card>
                <CardHeader>
                  <CardTitle>Request Volume</CardTitle>
                </CardHeader>
                <CardContent>
                  <RequestChart subnets={data.subnets} />
                </CardContent>
              </Card>

              {/* Latency Chart */}
              <Card>
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <CardTitle>Latency</CardTitle>
                    {data.subnets.length > 1 && (
                      <div
                        role="group"
                        aria-label="Subnet selector"
                        className="inline-flex items-center gap-1 rounded-md bg-elevated p-1"
                      >
                        {data.subnets.map((s) => (
                          <button
                            key={s.subnet_name}
                            type="button"
                            onClick={() => setSelectedSubnet(s.subnet_name)}
                            aria-pressed={
                              selectedSubnet === s.subnet_name ||
                              (!selectedSubnet &&
                                s.subnet_name === data.subnets![0].subnet_name)
                            }
                            className={cn(
                              "rounded-sm px-2 py-1 text-xs font-medium transition-colors",
                              "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary",
                              selectedSubnet === s.subnet_name ||
                                (!selectedSubnet &&
                                  s.subnet_name ===
                                    data.subnets![0].subnet_name)
                                ? "bg-background text-foreground shadow-sm"
                                : "text-muted-foreground hover:text-foreground",
                            )}
                          >
                            {SUBNET_DISPLAY_NAMES[s.subnet_name] ??
                              s.subnet_name}
                          </button>
                        ))}
                      </div>
                    )}
                  </div>
                </CardHeader>
                <CardContent>
                  <LatencyChart
                    subnets={data.subnets}
                    selectedSubnet={selectedSubnet}
                  />
                </CardContent>
              </Card>
            </>
          )}
        </div>
      )}
    </div>
  );
}

function EmptyState() {
  return (
    <div className="py-8 text-center">
      <p className="text-sm text-muted-foreground">
        No usage data yet. Make your first API request to see usage statistics.
      </p>
      <Link
        to="/dashboard"
        className="mt-2 inline-block text-sm font-medium text-indigo-600 hover:text-indigo-500"
      >
        Go to Quickstart
      </Link>
    </div>
  );
}
