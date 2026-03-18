export const SUBNET_DISPLAY_NAMES: Record<string, string> = {
  sn1: "Text Generation",
  sn19: "Image Generation",
  sn62: "Code Generation",
  "sn32-detect": "AI Detection",
  "sn22-search": "Web Search",
};

export const SUBNET_COLORS: Record<string, string> = {
  sn1: "#4f46e5",
  sn19: "#0891b2",
  sn62: "#7c3aed",
  "sn32-detect": "#dc2626",
  "sn22-search": "#059669",
};

export const SUBNET_RATE_LIMITS: Record<
  string,
  { minute: number; day: number }
> = {
  sn1: { minute: 10, day: 100 },
  sn19: { minute: 5, day: 50 },
  sn62: { minute: 10, day: 100 },
  "sn32-detect": { minute: 60, day: 600 },
  "sn22-search": { minute: 30, day: 300 },
};
