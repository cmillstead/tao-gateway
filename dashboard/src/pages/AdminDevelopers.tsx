import { useAdminDevelopers } from "@/hooks/useAdminDevelopers";
import { DeveloperSummaryCards } from "@/components/admin/DeveloperSummaryCards";
import { DeveloperTable } from "@/components/admin/DeveloperTable";

export function AdminDevelopers() {
  const { data, isLoading, error } = useAdminDevelopers();

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-foreground">
          Developer Activity
        </h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Track developer signups, activity, and per-subnet usage
        </p>
      </div>

      {error && (
        <div className="mb-4 rounded-md border border-destructive/30 bg-destructive/10 p-4" role="alert">
          <p className="text-sm text-destructive">
            Failed to load developer data: {error.message}
          </p>
        </div>
      )}

      {isLoading && (
        <div className="space-y-4">
          <div className="grid grid-cols-4 gap-4">
            {[1, 2, 3, 4].map((i) => (
              <div
                key={i}
                className="h-20 animate-pulse rounded-sm border border-border bg-elevated"
              />
            ))}
          </div>
          <div className="h-64 animate-pulse rounded-sm border border-border bg-elevated" />
        </div>
      )}

      {data && (
        <div className="space-y-6">
          <DeveloperSummaryCards metrics={data} />
          <DeveloperTable developers={data.developers} />
        </div>
      )}
    </div>
  );
}
