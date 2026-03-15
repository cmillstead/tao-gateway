import { cn } from "@/lib/utils";
import { SUBNET_DISPLAY_NAMES } from "./subnet-constants";

interface QuotaBarProps {
  subnetName: string;
  monthlyLimit: number;
  monthlyUsed: number;
  className?: string;
}

function getQuotaStatus(used: number, limit: number) {
  if (limit === 0) return { level: "normal" as const, label: "" };
  const pct = (used / limit) * 100;
  if (pct >= 100)
    return { level: "exceeded" as const, label: "Quota exceeded" };
  if (pct >= 80)
    return { level: "warning" as const, label: "Approaching limit" };
  return { level: "normal" as const, label: "" };
}

export function QuotaBar({
  subnetName,
  monthlyLimit,
  monthlyUsed,
  className,
}: QuotaBarProps) {
  const displayName = SUBNET_DISPLAY_NAMES[subnetName] ?? subnetName;
  const { level, label } = getQuotaStatus(monthlyUsed, monthlyLimit);
  const pct = monthlyLimit > 0 ? Math.min((monthlyUsed / monthlyLimit) * 100, 100) : 0;

  return (
    <div className={cn("space-y-1.5", className)}>
      <div className="flex items-center justify-between text-sm">
        <span className="font-medium text-foreground">{displayName}</span>
        <span className="tabular-nums text-muted-foreground">
          {monthlyUsed.toLocaleString()} / {monthlyLimit.toLocaleString()}{" "}
          monthly requests
        </span>
      </div>
      <div
        className="h-2 w-full overflow-hidden rounded-full bg-muted"
        role="progressbar"
        aria-valuenow={monthlyUsed}
        aria-valuemin={0}
        aria-valuemax={monthlyLimit}
        aria-label={`${displayName} quota: ${monthlyUsed} of ${monthlyLimit} used`}
      >
        <div
          className={cn(
            "h-full rounded-full transition-all",
            level === "normal" && "bg-indigo-600",
            level === "warning" && "bg-amber-500",
            level === "exceeded" && "bg-red-500",
          )}
          style={{ width: `${pct}%` }}
        />
      </div>
      {label && (
        <p
          className={cn(
            "text-xs font-medium",
            level === "warning" && "text-amber-600",
            level === "exceeded" && "text-red-600",
          )}
        >
          {label}
        </p>
      )}
    </div>
  );
}
