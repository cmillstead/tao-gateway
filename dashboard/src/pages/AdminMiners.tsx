import { useState } from "react";
import { useAdminMiners } from "@/hooks/useAdminMiners";
import { MinerTable } from "@/components/admin/MinerTable";
import { SUBNET_DISPLAY_NAMES } from "@/components/usage/subnet-constants";
import { cn } from "@/lib/utils";

export function AdminMiners() {
  const { data, isLoading, error } = useAdminMiners();
  const [selectedSubnet, setSelectedSubnet] = useState<string | null>(null);

  const subnetNames = data ? Object.keys(data.subnets).sort() : [];
  const activeSubnet = selectedSubnet ?? subnetNames[0] ?? null;

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-foreground">Miner Quality</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          View miner performance and quality scores per subnet
        </p>
      </div>

      {error && (
        <div className="mb-4 rounded-md border border-destructive/30 bg-destructive/10 p-4" role="alert">
          <p className="text-sm text-destructive">
            Failed to load miner data: {error.message}
          </p>
        </div>
      )}

      {isLoading && (
        <div className="space-y-4">
          <div className="h-10 w-64 animate-pulse rounded-sm bg-elevated" />
          <div className="h-64 animate-pulse rounded-sm border border-border bg-elevated" />
        </div>
      )}

      {data && (
        <div className="space-y-4">
          {/* Subnet tabs */}
          {subnetNames.length > 1 && (
            <div
              role="group"
              aria-label="Subnet selector"
              className="inline-flex items-center gap-1 rounded-md bg-elevated p-1"
            >
              {subnetNames.map((sn) => (
                <button
                  key={sn}
                  type="button"
                  onClick={() => setSelectedSubnet(sn)}
                  aria-pressed={activeSubnet === sn}
                  className={cn(
                    "rounded-sm px-3 py-1.5 text-sm font-medium transition-colors",
                    "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2",
                    activeSubnet === sn
                      ? "bg-background text-foreground shadow-sm"
                      : "text-muted-foreground hover:text-foreground",
                  )}
                >
                  {SUBNET_DISPLAY_NAMES[sn] ?? sn}
                </button>
              ))}
            </div>
          )}

          {activeSubnet && data.subnets[activeSubnet] ? (
            <>
              <h2 className="text-lg font-semibold text-foreground">
                {SUBNET_DISPLAY_NAMES[activeSubnet] ?? activeSubnet}
                <span className="ml-2 text-sm font-normal text-muted-foreground">
                  ({data.subnets[activeSubnet].length} miners)
                </span>
              </h2>
              <MinerTable miners={data.subnets[activeSubnet]} />
            </>
          ) : (
            <div className="py-8 text-center">
              <p className="text-sm text-muted-foreground">
                No miner data available.
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
