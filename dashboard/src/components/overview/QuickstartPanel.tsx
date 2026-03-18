import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Button } from "@/components/ui/button";
import { CodeSnippet } from "./CodeSnippet";
import { useNavigate } from "react-router-dom";

const API_BASE_URL = "https://api.taogateway.com";

interface QuickstartPanelProps {
  apiKeyPrefix: string | null;
}

function getKeyPlaceholder(prefix: string | null): string {
  if (prefix) return prefix + "...";
  return "<YOUR_API_KEY>";
}

function getDetectionCurlSnippet(keyDisplay: string): string {
  return `curl -X POST ${API_BASE_URL}/v1/moderations \\
  -H "Authorization: Bearer ${keyDisplay}" \\
  -H "Content-Type: application/json" \\
  -d '{
    "model": "tao-sn32",
    "input": ["Is this text written by AI?"]
  }'`;
}

function getDetectionPythonSnippet(keyDisplay: string): string {
  return `import httpx

response = httpx.post(
    "${API_BASE_URL}/v1/moderations",
    headers={"Authorization": "Bearer ${keyDisplay}"},
    json={"model": "tao-sn32", "input": ["Is this text written by AI?"]},
)
result = response.json()["results"][0]
print(f"AI generated: {result['flagged']} (score: {result['category_scores']['ai_generated']})")`;
}

function getSearchCurlSnippet(keyDisplay: string): string {
  return `curl -X POST ${API_BASE_URL}/v1/search \\
  -H "Authorization: Bearer ${keyDisplay}" \\
  -H "Content-Type: application/json" \\
  -d '{
    "model": "tao-sn22",
    "query": "bittensor subnets",
    "num_results": 5
  }'`;
}

function getSearchPythonSnippet(keyDisplay: string): string {
  return `import httpx

response = httpx.post(
    "${API_BASE_URL}/v1/search",
    headers={"Authorization": "Bearer ${keyDisplay}"},
    json={"model": "tao-sn22", "query": "bittensor subnets", "num_results": 5},
)
for result in response.json()["results"]:
    print(f"{result['position']}. {result['title']} — {result['url']}")`;
}

export function QuickstartPanel({ apiKeyPrefix }: QuickstartPanelProps) {
  const navigate = useNavigate();

  if (!apiKeyPrefix) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Quickstart</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">
            Create an API key to see quickstart examples with your key pre-filled.
          </p>
          <Button
            className="mt-3"
            onClick={() => navigate("/dashboard/api-keys")}
          >
            Create API Key
          </Button>
        </CardContent>
      </Card>
    );
  }

  const keyDisplay = getKeyPlaceholder(apiKeyPrefix);

  return (
    <Card>
      <CardHeader>
        <CardTitle>Quickstart</CardTitle>
      </CardHeader>
      <CardContent>
        <p className="mb-3 text-sm text-muted-foreground">
          Replace the key prefix below with your full API key (copied at creation time).
        </p>
        <Tabs defaultValue="detection-curl">
          <TabsList className="flex-wrap h-auto gap-1">
            <TabsTrigger value="detection-curl">Detection (curl)</TabsTrigger>
            <TabsTrigger value="detection-python">Detection (Python)</TabsTrigger>
            <TabsTrigger value="search-curl">Search (curl)</TabsTrigger>
            <TabsTrigger value="search-python">Search (Python)</TabsTrigger>
          </TabsList>
          <TabsContent value="detection-curl">
            <CodeSnippet code={getDetectionCurlSnippet(keyDisplay)} language="bash" />
          </TabsContent>
          <TabsContent value="detection-python">
            <CodeSnippet code={getDetectionPythonSnippet(keyDisplay)} language="python" />
          </TabsContent>
          <TabsContent value="search-curl">
            <CodeSnippet code={getSearchCurlSnippet(keyDisplay)} language="bash" />
          </TabsContent>
          <TabsContent value="search-python">
            <CodeSnippet code={getSearchPythonSnippet(keyDisplay)} language="python" />
          </TabsContent>
        </Tabs>
      </CardContent>
    </Card>
  );
}
