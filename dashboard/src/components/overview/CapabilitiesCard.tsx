import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { SubnetStatusBadge } from "./SubnetStatusBadge";
import type { SubnetOverview } from "@/types";

interface CapabilitiesCardProps {
  subnets: SubnetOverview[];
}

export function CapabilitiesCard({ subnets }: CapabilitiesCardProps) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Capabilities</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="space-y-3">
          {subnets.map((subnet) => (
            <div
              key={subnet.netuid}
              className="flex items-center justify-between"
            >
              <span className="text-sm font-medium text-foreground">
                {subnet.name}{" "}
                <span className="text-muted-foreground">(SN{subnet.netuid})</span>
              </span>
              <SubnetStatusBadge status={subnet.status} />
            </div>
          ))}
          {subnets.length === 0 && (
            <p className="text-sm text-muted-foreground">No subnets available</p>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
