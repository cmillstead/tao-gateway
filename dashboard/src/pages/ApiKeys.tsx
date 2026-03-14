import { useState } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { ApiKeyTable } from "@/components/api-keys/ApiKeyTable";
import { CreateKeyDialog } from "@/components/api-keys/CreateKeyDialog";
import { useApiKeys } from "@/hooks/useApiKeys";
import { Plus } from "lucide-react";

export function ApiKeys() {
  const [createOpen, setCreateOpen] = useState(false);
  const { data, isLoading, error } = useApiKeys();

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-bold text-foreground">API Keys</h1>
        <Button onClick={() => setCreateOpen(true)}>
          <Plus className="mr-2 h-4 w-4" />
          Create API Key
        </Button>
      </div>

      <Card>
        <CardContent className="p-0">
          {isLoading && (
            <div className="flex items-center justify-center py-12" aria-live="polite">
              <p className="text-muted-foreground">Loading keys...</p>
            </div>
          )}
          {error && (
            <div className="flex items-center justify-center py-12">
              <p className="text-destructive" role="alert">
                Failed to load API keys. Please try again.
              </p>
            </div>
          )}
          {data && (
            <ApiKeyTable
              keys={data.items}
              onCreateClick={() => setCreateOpen(true)}
            />
          )}
        </CardContent>
      </Card>

      <CreateKeyDialog open={createOpen} onOpenChange={setCreateOpen} />
    </div>
  );
}
