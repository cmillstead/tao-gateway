import { useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { ApiKeyDisplay } from "./ApiKeyDisplay";
import { useRotateApiKey } from "@/hooks/useApiKeys";

interface RotateKeyDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  keyId: string;
  keyPrefix: string;
}

export function RotateKeyDialog({
  open,
  onOpenChange,
  keyId,
  keyPrefix,
}: RotateKeyDialogProps) {
  const [newKey, setNewKey] = useState<string | null>(null);
  const rotateMutation = useRotateApiKey();

  const handleRotate = async () => {
    try {
      const result = await rotateMutation.mutateAsync(keyId);
      setNewKey(result.new_key.key);
    } catch {
      // Error state handled by rotateMutation.isError
    }
  };

  const handleClose = () => {
    setNewKey(null);
    rotateMutation.reset();
    onOpenChange(false);
  };

  const isKeyDisplayed = newKey !== null;

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent
        onClose={handleClose}
        preventBackdropClose={isKeyDisplayed}
        preventEscapeClose={isKeyDisplayed}
      >
        <DialogHeader>
          <DialogTitle>
            {isKeyDisplayed ? "Key Rotated" : "Rotate API Key"}
          </DialogTitle>
          {!isKeyDisplayed && (
            <DialogDescription>
              This will create a new key and immediately revoke{" "}
              <code className="font-mono text-sm">{keyPrefix}...</code>.
              Active integrations using this key will stop working.
            </DialogDescription>
          )}
        </DialogHeader>

        {isKeyDisplayed ? (
          <div className="space-y-4">
            <div className="rounded-md border border-border bg-surface p-4">
              <ApiKeyDisplay value={newKey} isFull />
            </div>
            <p className="text-sm font-medium text-destructive">
              This key won't be shown again. Copy it now.
            </p>
            <DialogFooter>
              <Button onClick={handleClose}>Done</Button>
            </DialogFooter>
          </div>
        ) : (
          <>
            {rotateMutation.isError && (
              <p className="text-sm text-destructive" role="alert">
                {rotateMutation.error.message}
              </p>
            )}
            <DialogFooter>
              <Button variant="outline" onClick={handleClose}>
                Cancel
              </Button>
              <Button
                variant="destructive"
                onClick={handleRotate}
                disabled={rotateMutation.isPending}
              >
                {rotateMutation.isPending ? "Rotating..." : "Rotate Key"}
              </Button>
            </DialogFooter>
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}
