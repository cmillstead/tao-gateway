import { useState } from "react";
import {
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableHead,
  TableCell,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Tooltip } from "@/components/ui/tooltip";
import { ApiKeyDisplay } from "./ApiKeyDisplay";
import { RotateKeyDialog } from "./RotateKeyDialog";
import { RevokeKeyDialog } from "./RevokeKeyDialog";
import { RefreshCw, Trash2 } from "lucide-react";
import type { ApiKey } from "@/types";

function formatDate(dateStr: string): string {
  const date = new Date(dateStr);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();

  // Guard against future dates (clock skew)
  if (diffMs < 0) return "Just now";

  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMs / 3600000);
  const diffDays = Math.floor(diffMs / 86400000);

  if (diffMins < 1) return "Just now";
  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  if (diffDays < 7) return `${diffDays}d ago`;

  return date.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

interface ApiKeyTableProps {
  keys: ApiKey[];
  onCreateClick: () => void;
}

export function ApiKeyTable({ keys, onCreateClick }: ApiKeyTableProps) {
  const [rotateTarget, setRotateTarget] = useState<ApiKey | null>(null);
  const [revokeTarget, setRevokeTarget] = useState<ApiKey | null>(null);

  if (keys.length === 0) {
    return (
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Name</TableHead>
            <TableHead>Key</TableHead>
            <TableHead>Status</TableHead>
            <TableHead>Created</TableHead>
            <TableHead className="text-right">Actions</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          <TableRow>
            <TableCell colSpan={5} className="py-12 text-center">
              <p className="text-muted-foreground">
                No API keys yet. Create one to get started.
              </p>
              <Button className="mt-4" onClick={onCreateClick}>
                Create API Key
              </Button>
            </TableCell>
          </TableRow>
        </TableBody>
      </Table>
    );
  }

  return (
    <>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Name</TableHead>
            <TableHead>Key</TableHead>
            <TableHead>Status</TableHead>
            <TableHead>Created</TableHead>
            <TableHead className="text-right">Actions</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {keys.map((key) => (
            <TableRow key={key.id}>
              <TableCell className="font-medium">
                {key.name ?? "—"}
              </TableCell>
              <TableCell>
                <ApiKeyDisplay value={key.prefix} />
              </TableCell>
              <TableCell>
                {key.is_active ? (
                  <Badge variant="success">
                    <span className="inline-block h-2 w-2 rounded-full bg-emerald-500" aria-hidden="true" />
                    Active
                  </Badge>
                ) : (
                  <Badge variant="destructive">
                    <span className="inline-block h-2 w-2 rounded-full bg-red-500" aria-hidden="true" />
                    Revoked
                  </Badge>
                )}
              </TableCell>
              <TableCell className="text-muted-foreground">
                {formatDate(key.created_at)}
              </TableCell>
              <TableCell className="text-right">
                {key.is_active && (
                  <span className="inline-flex gap-1">
                    <Tooltip content="Rotate">
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-8 w-8"
                        onClick={() => setRotateTarget(key)}
                        aria-label="Rotate key"
                      >
                        <RefreshCw className="h-4 w-4" />
                      </Button>
                    </Tooltip>
                    <Tooltip content="Revoke">
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-8 w-8 text-destructive hover:text-destructive"
                        onClick={() => setRevokeTarget(key)}
                        aria-label="Revoke key"
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </Tooltip>
                  </span>
                )}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>

      {rotateTarget && (
        <RotateKeyDialog
          open={!!rotateTarget}
          onOpenChange={(open) => !open && setRotateTarget(null)}
          keyId={rotateTarget.id}
          keyPrefix={rotateTarget.prefix}
        />
      )}

      {revokeTarget && (
        <RevokeKeyDialog
          open={!!revokeTarget}
          onOpenChange={(open) => !open && setRevokeTarget(null)}
          keyId={revokeTarget.id}
          keyPrefix={revokeTarget.prefix}
        />
      )}
    </>
  );
}
