import {
  AlertDialog,
  AlertDialogContent,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogDescription,
  AlertDialogFooter,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import { useRevokeApiKey } from "@/hooks/useApiKeys";

interface RevokeKeyDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  keyId: string;
  keyPrefix: string;
}

export function RevokeKeyDialog({
  open,
  onOpenChange,
  keyId,
  keyPrefix,
}: RevokeKeyDialogProps) {
  const revokeMutation = useRevokeApiKey();

  const handleRevoke = async () => {
    try {
      await revokeMutation.mutateAsync(keyId);
      onOpenChange(false);
      revokeMutation.reset();
    } catch {
      // Error state handled by revokeMutation.isError
    }
  };

  const handleCancel = () => {
    revokeMutation.reset();
    onOpenChange(false);
  };

  return (
    <AlertDialog open={open} onOpenChange={onOpenChange}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Revoke API Key</AlertDialogTitle>
          <AlertDialogDescription>
            This will immediately invalidate{" "}
            <code className="font-mono text-sm">{keyPrefix}...</code>.
            Active integrations using this key will stop working.
            This action cannot be undone.
          </AlertDialogDescription>
        </AlertDialogHeader>
        {revokeMutation.isError && (
          <p className="text-sm text-destructive" role="alert">
            {revokeMutation.error.message}
          </p>
        )}
        <AlertDialogFooter>
          <Button variant="outline" onClick={handleCancel}>
            Cancel
          </Button>
          <Button
            variant="destructive"
            onClick={handleRevoke}
            disabled={revokeMutation.isPending}
          >
            {revokeMutation.isPending ? "Revoking..." : "Revoke Key"}
          </Button>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
