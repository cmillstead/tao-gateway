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

function getCurlSnippet(keyDisplay: string): string {
  return `curl -X POST ${API_BASE_URL}/v1/chat/completions \\
  -H "Authorization: Bearer ${keyDisplay}" \\
  -H "Content-Type: application/json" \\
  -d '{
    "model": "tao-text",
    "messages": [{"role": "user", "content": "Hello"}]
  }'`;
}

function getPythonSnippet(keyDisplay: string): string {
  return `from openai import OpenAI

client = OpenAI(
    base_url="${API_BASE_URL}/v1",
    api_key="${keyDisplay}",
)

response = client.chat.completions.create(
    model="tao-text",
    messages=[{"role": "user", "content": "Hello"}],
)
print(response.choices[0].message.content)`;
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
        <Tabs defaultValue="curl">
          <TabsList>
            <TabsTrigger value="curl">curl</TabsTrigger>
            <TabsTrigger value="python">Python</TabsTrigger>
          </TabsList>
          <TabsContent value="curl">
            <CodeSnippet code={getCurlSnippet(keyDisplay)} language="bash" />
          </TabsContent>
          <TabsContent value="python">
            <CodeSnippet code={getPythonSnippet(keyDisplay)} language="python" />
          </TabsContent>
        </Tabs>
      </CardContent>
    </Card>
  );
}
