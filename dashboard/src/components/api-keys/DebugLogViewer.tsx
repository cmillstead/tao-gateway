import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { useDebugLogs } from "@/hooks/useDebugLogs";
import type { DebugLogEntry } from "@/types";

interface DebugLogViewerProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  keyId: string;
  keyPrefix: string;
}

function formatTimestamp(dateStr: string): string {
  return new Date(dateStr).toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

function LogEntry({ entry }: { entry: DebugLogEntry }) {
  return (
    <div className="rounded-lg border border-border p-4 space-y-3">
      <div className="flex items-center justify-between text-sm text-muted-foreground">
        <span>{formatTimestamp(entry.created_at)}</span>
      </div>
      {entry.request_body && (
        <div>
          <p className="text-xs font-medium text-muted-foreground mb-1">Request</p>
          <pre className="rounded bg-muted p-3 text-xs overflow-x-auto max-h-48 overflow-y-auto">
            {entry.request_body}
          </pre>
        </div>
      )}
      {entry.response_body && (
        <div>
          <p className="text-xs font-medium text-muted-foreground mb-1">Response</p>
          <pre className="rounded bg-muted p-3 text-xs overflow-x-auto max-h-48 overflow-y-auto">
            {entry.response_body}
          </pre>
        </div>
      )}
    </div>
  );
}

export function DebugLogViewer({ open, onOpenChange, keyId, keyPrefix }: DebugLogViewerProps) {
  const { data, isLoading, error } = useDebugLogs(open ? keyId : null);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl max-h-[80vh] overflow-y-auto" onClose={() => onOpenChange(false)}>
        <DialogHeader>
          <DialogTitle>Debug Logs</DialogTitle>
          <DialogDescription>
            Recent request/response content for {keyPrefix}. Logs are automatically deleted after 48 hours.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 mt-4">
          {isLoading && (
            <div className="text-center py-8 text-muted-foreground">Loading debug logs...</div>
          )}

          {error && (
            <div className="rounded-lg border border-destructive bg-destructive/10 p-4 text-sm text-destructive">
              Failed to load debug logs. Please try again.
            </div>
          )}

          {data && data.items.length === 0 && (
            <div className="text-center py-8 text-muted-foreground">
              No debug logs yet. Send a request with this key to see content here.
            </div>
          )}

          {data && data.items.length > 0 && (
            <>
              <p className="text-sm text-muted-foreground">
                Showing {data.items.length} of {data.total} entries
              </p>
              {data.items.map((entry) => (
                <LogEntry key={entry.id} entry={entry} />
              ))}
            </>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
