import { useAdminMetagraph } from "@/hooks/useAdminMetagraph";
import { MetagraphStatusCard } from "@/components/admin/MetagraphStatusCard";

export function AdminMetagraph() {
  const { data, isLoading, error } = useAdminMetagraph();

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-foreground">Metagraph Status</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Monitor metagraph sync freshness across subnets
        </p>
      </div>

      {error && (
        <div className="mb-4 rounded-md border border-destructive/30 bg-destructive/10 p-4" role="alert">
          <p className="text-sm text-destructive">
            Failed to load metagraph status: {error.message}
          </p>
        </div>
      )}

      {isLoading && (
        <div className="space-y-4">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-32 animate-pulse rounded-sm border border-border bg-elevated" />
          ))}
        </div>
      )}

      {data && (
        <div className="space-y-4">
          {data.subnets.map((subnet) => (
            <MetagraphStatusCard key={subnet.netuid} subnet={subnet} />
          ))}
          {data.subnets.length === 0 && (
            <div className="py-8 text-center">
              <p className="text-sm text-muted-foreground">
                No metagraph data available.
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
