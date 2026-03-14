import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

export function ApiKeys() {
  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-bold text-foreground">API Keys</h1>
        <Button disabled>Create Key</Button>
      </div>
      <Card>
        <CardHeader>
          <CardTitle>API Keys</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-muted-foreground">Coming in Story 4.2</p>
        </CardContent>
      </Card>
    </div>
  );
}
