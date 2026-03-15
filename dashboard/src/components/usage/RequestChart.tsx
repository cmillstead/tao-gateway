import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";
import type { SubnetUsageWithQuota } from "@/types";
import { SUBNET_COLORS, SUBNET_DISPLAY_NAMES } from "./subnet-constants";

interface RequestChartProps {
  subnets: SubnetUsageWithQuota[];
}

function transformData(subnets: SubnetUsageWithQuota[]) {
  const dateMap = new Map<string, Record<string, number>>();

  for (const subnet of subnets) {
    for (const summary of subnet.summaries ?? []) {
      const existing = dateMap.get(summary.period) ?? {};
      existing[subnet.subnet_name] = summary.request_count;
      dateMap.set(summary.period, existing);
    }
  }

  return Array.from(dateMap.entries())
    .map(([date, counts]) => ({ date, ...counts }))
    .sort((a, b) => a.date.localeCompare(b.date));
}

export function RequestChart({ subnets }: RequestChartProps) {
  const data = transformData(subnets);
  const subnetNames = subnets.map((s) => s.subnet_name);

  if (data.length === 0) return null;

  return (
    <ResponsiveContainer width="100%" height={300}>
      <AreaChart
        data={data}
        margin={{ top: 5, right: 20, left: 0, bottom: 5 }}
        accessibilityLayer
      >
        <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
        <XAxis
          dataKey="date"
          className="text-xs"
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
          className="text-xs"
          tick={{ fill: "var(--color-muted-foreground)", fontSize: 12 }}
          allowDecimals={false}
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
            Number(value).toLocaleString(),
            SUBNET_DISPLAY_NAMES[String(name)] ?? String(name),
          ]}
        />
        <Legend
          formatter={(value: string) =>
            SUBNET_DISPLAY_NAMES[value] ?? value
          }
        />
        {subnetNames.map((name) => (
          <Area
            key={name}
            type="monotone"
            dataKey={name}
            stroke={SUBNET_COLORS[name] ?? "#6b7280"}
            fill={SUBNET_COLORS[name] ?? "#6b7280"}
            fillOpacity={0.1}
            strokeWidth={2}
          />
        ))}
      </AreaChart>
    </ResponsiveContainer>
  );
}
