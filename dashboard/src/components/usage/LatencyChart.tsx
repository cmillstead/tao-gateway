import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";
import type { SubnetUsageWithQuota } from "@/types";
import { SUBNET_DISPLAY_NAMES } from "./subnet-constants";

const PERCENTILE_COLORS = {
  p50: "#10b981",
  p95: "#f59e0b",
  p99: "#ef4444",
};

interface LatencyChartProps {
  subnets: SubnetUsageWithQuota[];
  selectedSubnet?: string;
}

function transformLatencyData(subnet: SubnetUsageWithQuota) {
  return (subnet.summaries ?? [])
    .map((s) => ({
      date: s.period,
      p50: s.p50_latency_ms,
      p95: s.p95_latency_ms,
      p99: s.p99_latency_ms,
    }))
    .sort((a, b) => a.date.localeCompare(b.date));
}

export function LatencyChart({ subnets, selectedSubnet }: LatencyChartProps) {
  const subnet =
    subnets.find((s) => s.subnet_name === selectedSubnet) ?? subnets[0];
  if (!subnet) return null;

  const data = transformLatencyData(subnet);
  if (data.length === 0) return null;

  const displayName =
    SUBNET_DISPLAY_NAMES[subnet.subnet_name] ?? subnet.subnet_name;

  return (
    <div>
      <p className="mb-2 text-sm text-muted-foreground">
        Latency for {displayName} (ms)
      </p>
      <ResponsiveContainer width="100%" height={250}>
        <LineChart
          data={data}
          margin={{ top: 5, right: 20, left: 0, bottom: 5 }}
          accessibilityLayer
        >
          <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
          <XAxis
            dataKey="date"
            tick={{ fill: "var(--color-muted-foreground)", fontSize: 12 }}
            tickFormatter={(value: string) => {
              const d = new Date(value + "T00:00:00");
              return d.toLocaleDateString(undefined, {
                month: "short",
                day: "numeric",
              });
            }}
          />
          <YAxis
            tick={{ fill: "var(--color-muted-foreground)", fontSize: 12 }}
            unit="ms"
          />
          <Tooltip
            contentStyle={{
              backgroundColor: "var(--color-background)",
              border: "1px solid var(--color-border)",
              borderRadius: "4px",
              fontSize: "12px",
            }}
            labelFormatter={(value) => {
              const d = new Date(String(value) + "T00:00:00");
              return d.toLocaleDateString(undefined, {
                month: "long",
                day: "numeric",
                year: "numeric",
              });
            }}
            formatter={(value, name) => [
              `${Number(value).toLocaleString()} ms`,
              String(name).toUpperCase(),
            ]}
          />
          <Legend formatter={(value: string) => value.toUpperCase()} />
          <Line
            type="monotone"
            dataKey="p50"
            stroke={PERCENTILE_COLORS.p50}
            strokeWidth={2}
            dot={false}
          />
          <Line
            type="monotone"
            dataKey="p95"
            stroke={PERCENTILE_COLORS.p95}
            strokeWidth={2}
            dot={false}
          />
          <Line
            type="monotone"
            dataKey="p99"
            stroke={PERCENTILE_COLORS.p99}
            strokeWidth={2}
            dot={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
