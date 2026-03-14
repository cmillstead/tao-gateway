import { useOverview } from "@/hooks/useOverview";
import { MetricCard } from "@/components/overview/MetricCard";
import { CapabilitiesCard } from "@/components/overview/CapabilitiesCard";
import { RateLimitsCard } from "@/components/overview/RateLimitsCard";
import { QuickstartPanel } from "@/components/overview/QuickstartPanel";

export function Dashboard() {
  const { data, isLoading, error } = useOverview();

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-foreground">Overview</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Welcome to TaoGateway
        </p>
      </div>

      {error && (
        <div className="mb-4 rounded-md bg-red-50 p-4" role="alert">
          <p className="text-sm text-red-700">
            Failed to load overview: {error.message}
          </p>
        </div>
      )}

      {isLoading && (
        <div className="space-y-4">
          <div className="grid gap-4 sm:grid-cols-3">
            {[1, 2, 3].map((i) => (
              <div
                key={i}
                className="h-24 animate-pulse rounded-sm border border-border bg-elevated"
              />
            ))}
          </div>
          <div className="h-48 animate-pulse rounded-sm border border-border bg-elevated" />
          <div className="h-48 animate-pulse rounded-sm border border-border bg-elevated" />
        </div>
      )}

      {data && (
        <div className="space-y-4">
          <div className="grid gap-4 sm:grid-cols-3">
            <MetricCard
              label="Current Tier"
              value={data.tier.charAt(0).toUpperCase() + data.tier.slice(1)}
              subtitle="Usage-based pricing coming soon"
            />
            <MetricCard
              label="Active Keys"
              value={data.api_key_count}
            />
            <MetricCard
              label="Available Subnets"
              value={data.subnets.length}
            />
          </div>

          <CapabilitiesCard subnets={data.subnets} />

          <QuickstartPanel apiKeyPrefix={data.first_api_key_prefix} />

          <RateLimitsCard subnets={data.subnets} />
        </div>
      )}
    </div>
  );
}
