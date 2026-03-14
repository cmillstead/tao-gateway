import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export function Usage() {
  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-foreground">Usage</h1>
      </div>
      <Card>
        <CardHeader>
          <CardTitle>Usage Analytics</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-muted-foreground">Coming in Story 5.2</p>
        </CardContent>
      </Card>
    </div>
  );
}
