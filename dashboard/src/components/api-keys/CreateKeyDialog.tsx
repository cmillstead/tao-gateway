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
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ApiKeyDisplay } from "./ApiKeyDisplay";
import { useCreateApiKey } from "@/hooks/useApiKeys";

interface CreateKeyDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function CreateKeyDialog({ open, onOpenChange }: CreateKeyDialogProps) {
  const [name, setName] = useState("");
  const [createdKey, setCreatedKey] = useState<string | null>(null);
  const createMutation = useCreateApiKey();

  const handleGenerate = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const result = await createMutation.mutateAsync({
        environment: "live",
        name: name.trim() || undefined,
      });
      setCreatedKey(result.key);
    } catch {
      // Error state handled by createMutation.isError
    }
  };

  const handleClose = () => {
    setName("");
    setCreatedKey(null);
    createMutation.reset();
    onOpenChange(false);
  };

  const isKeyDisplayed = createdKey !== null;

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent
        onClose={handleClose}
        preventBackdropClose={isKeyDisplayed}
        preventEscapeClose={isKeyDisplayed}
      >
        <DialogHeader>
          <DialogTitle>
            {isKeyDisplayed ? "API Key Created" : "Create API Key"}
          </DialogTitle>
          {!isKeyDisplayed && (
            <DialogDescription>
              Generate a new API key for your application.
            </DialogDescription>
          )}
        </DialogHeader>

        {isKeyDisplayed ? (
          <div className="space-y-4">
            <div className="rounded-md border border-border bg-surface p-4">
              <ApiKeyDisplay value={createdKey} isFull />
            </div>
            <p className="text-sm font-medium text-destructive">
              This key won't be shown again. Copy it now.
            </p>
            <DialogFooter>
              <Button onClick={handleClose}>Done</Button>
            </DialogFooter>
          </div>
        ) : (
          <form onSubmit={handleGenerate}>
            <div className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="key-name">
                  Name <span className="text-muted-foreground">(optional)</span>
                </Label>
                <Input
                  id="key-name"
                  placeholder="e.g., production, testing"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  maxLength={100}
                  autoFocus
                />
              </div>
              {createMutation.isError && (
                <p className="text-sm text-destructive" role="alert">
                  {createMutation.error.message}
                </p>
              )}
            </div>
            <DialogFooter>
              <Button
                type="submit"
                disabled={createMutation.isPending}
              >
                {createMutation.isPending ? "Generating..." : "Generate Key"}
              </Button>
            </DialogFooter>
          </form>
        )}
      </DialogContent>
    </Dialog>
  );
}
