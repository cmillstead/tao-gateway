import { cn } from "@/lib/utils";

type SubnetStatus = "healthy" | "degraded" | "unavailable";

interface SubnetStatusBadgeProps {
  status: SubnetStatus;
  className?: string;
}

const STATUS_CONFIG: Record<SubnetStatus, { dotColor: string; label: string }> = {
  healthy: { dotColor: "bg-emerald-500", label: "Healthy" },
  degraded: { dotColor: "bg-amber-500", label: "Degraded" },
  unavailable: { dotColor: "bg-red-500", label: "Down" },
};

export function SubnetStatusBadge({ status, className }: SubnetStatusBadgeProps) {
  const config = STATUS_CONFIG[status];

  return (
    <span className={cn("inline-flex items-center gap-1.5 text-sm", className)}>
      <span
        className={cn("h-2 w-2 rounded-full", config.dotColor)}
        aria-hidden="true"
      />
      <span>{config.label}</span>
    </span>
  );
}
