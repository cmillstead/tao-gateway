import { useState, useCallback, useRef, useEffect } from "react";
import { Copy, Check } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Tooltip } from "@/components/ui/tooltip";

interface ApiKeyDisplayProps {
  value: string;
  isFull?: boolean;
}

export function ApiKeyDisplay({ value, isFull = false }: ApiKeyDisplayProps) {
  const [copied, setCopied] = useState(false);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const codeRef = useRef<HTMLElement>(null);

  // Clear timer on unmount
  useEffect(() => {
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, []);

  const handleCopy = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(true);
      if (timerRef.current) clearTimeout(timerRef.current);
      timerRef.current = setTimeout(() => setCopied(false), 2000);
    } catch {
      // Fallback: select text for manual copy
      const el = codeRef.current;
      if (el) {
        const range = document.createRange();
        range.selectNodeContents(el);
        const selection = window.getSelection();
        selection?.removeAllRanges();
        selection?.addRange(range);
      }
    }
  }, [value]);

  const displayValue = isFull ? value : value.slice(0, 20) + "...";

  return (
    <span className="inline-flex items-center gap-1.5">
      <code ref={codeRef} className="font-mono text-sm text-foreground">
        {displayValue}
      </code>
      <Tooltip content={copied ? "Copied" : "Copy"}>
        <Button
          variant="ghost"
          size="icon"
          className="h-7 w-7"
          onClick={handleCopy}
          aria-label={copied ? "Copied" : "Copy key"}
        >
          {copied ? (
            <Check className="h-3.5 w-3.5 text-success" />
          ) : (
            <Copy className="h-3.5 w-3.5" />
          )}
        </Button>
      </Tooltip>
      <span className="sr-only" aria-live="polite">
        {copied ? "Key copied to clipboard" : ""}
      </span>
    </span>
  );
}
