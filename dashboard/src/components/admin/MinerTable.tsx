import { useMemo } from "react";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import type { MinerInfo } from "@/types/admin";

interface MinerTableProps {
  miners: MinerInfo[];
}

const HIGH_ERROR_RATE_THRESHOLD = 0.2;

export function MinerTable({ miners }: MinerTableProps) {
  const sorted = useMemo(
    () => [...miners].sort((a, b) => b.gateway_quality_score - a.gateway_quality_score),
    [miners],
  );

  if (miners.length === 0) {
    return (
      <div className="py-8 text-center">
        <p className="text-sm text-muted-foreground">No miners available.</p>
      </div>
    );
  }

  return (
    <div className="overflow-x-auto rounded-md border border-border">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>UID</TableHead>
            <TableHead>Hotkey</TableHead>
            <TableHead className="text-right">Incentive</TableHead>
            <TableHead className="text-right">Quality Score</TableHead>
            <TableHead className="text-right">Requests</TableHead>
            <TableHead className="text-right">Avg Latency</TableHead>
            <TableHead className="text-right">Error Rate</TableHead>
            <TableHead>Status</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {sorted.map((miner) => {
            const isHighError = miner.error_rate > HIGH_ERROR_RATE_THRESHOLD;
            const isInactive = miner.total_requests === 0;

            return (
              <TableRow
                key={miner.miner_uid}
                className={cn(isInactive && "opacity-50")}
              >
                <TableCell className="font-medium">{miner.miner_uid}</TableCell>
                <TableCell
                  className="font-mono text-xs"
                  title={miner.hotkey}
                >
                  {miner.hotkey.slice(0, 8)}...{miner.hotkey.slice(-6)}
                </TableCell>
                <TableCell className="text-right">
                  {miner.incentive_score.toFixed(4)}
                </TableCell>
                <TableCell className="text-right">
                  {miner.gateway_quality_score.toFixed(2)}
                </TableCell>
                <TableCell className="text-right">
                  {miner.total_requests.toLocaleString()}
                </TableCell>
                <TableCell className="text-right">
                  {miner.avg_latency_ms.toFixed(0)}ms
                </TableCell>
                <TableCell className="text-right">
                  {(miner.error_rate * 100).toFixed(1)}%
                </TableCell>
                <TableCell>
                  {isHighError && (
                    <Badge variant="destructive" className="text-xs">
                      High Errors
                    </Badge>
                  )}
                  {isInactive && (
                    <Badge variant="outline" className="text-xs">
                      Inactive
                    </Badge>
                  )}
                </TableCell>
              </TableRow>
            );
          })}
        </TableBody>
      </Table>
    </div>
  );
}
