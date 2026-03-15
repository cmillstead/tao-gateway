import { Card, CardContent } from "@/components/ui/card";
import type { DeveloperMetrics } from "@/types/admin";

interface DeveloperSummaryCardsProps {
  metrics: DeveloperMetrics;
}

export function DeveloperSummaryCards({ metrics }: DeveloperSummaryCardsProps) {
  const cards = [
    { label: "Total Developers", value: metrics.total_developers },
    { label: "New Today", value: metrics.new_signups_today },
    { label: "New This Week", value: metrics.new_signups_this_week },
    { label: "Weekly Active", value: metrics.weekly_active_developers },
  ];

  return (
    <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
      {cards.map((card) => (
        <Card key={card.label}>
          <CardContent className="pt-6">
            <p className="text-xs text-muted-foreground">{card.label}</p>
            <p className="text-2xl font-bold text-foreground">
              {card.value.toLocaleString()}
            </p>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
