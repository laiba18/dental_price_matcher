import type { QuotaAlert } from "./types";

const SERVICE_LABELS: Record<string, string> = {
  groq: "Groq",
  gemini: "Gemini",
  firecrawl: "Firecrawl",
  serpapi: "SerpAPI",
  openai: "OpenAI",
  openrouter: "OpenRouter",
};

export function quotaAlertFromEvent(data: Record<string, unknown>): QuotaAlert {
  return {
    service: String(data.service ?? "unknown"),
    kind: String(data.kind ?? "credits"),
    message: String(data.message ?? "API credit limit reached."),
    detail: data.detail ? String(data.detail) : undefined,
  };
}

export function quotaAlertFromFirecrawlSummary(data: Record<string, unknown>): QuotaAlert | null {
  if (!data.exhausted) return null;
  const reason = String(data.exhausted_reason ?? "");
  if (reason === "402") {
    return {
      service: "firecrawl",
      kind: "credits",
      message: "Your Firecrawl credit limit has been reached.",
      detail: "Web page scraping was paused during this run.",
    };
  }
  if (reason === "budget") {
    return {
      service: "firecrawl",
      kind: "budget",
      message: "The Firecrawl scrape limit for this run has been reached.",
      detail: "Remaining pages used cached or free-fetch data only.",
    };
  }
  return null;
}

export function quotaAlertsFromError(error: string): QuotaAlert[] {
  const lower = error.toLowerCase();
  const alerts: QuotaAlert[] = [];

  const checks: Array<{ match: RegExp; service: string; message: string }> = [
    { match: /firecrawl|402/, service: "firecrawl", message: "Your Firecrawl credit limit has been reached." },
    { match: /serpapi/, service: "serpapi", message: "Your SerpAPI credit limit has been reached." },
    { match: /gemini/, service: "gemini", message: "Your Gemini API credit or rate limit has been reached." },
    { match: /groq|rate.?limit|quota/, service: "groq", message: "Your Groq API credit or rate limit has been reached." },
  ];

  for (const { match, service, message } of checks) {
    if (match.test(lower) && !alerts.some((a) => a.service === service)) {
      alerts.push({
        service,
        kind: "credits",
        message,
        detail: `Check your ${SERVICE_LABELS[service] ?? service} plan or wait for the limit to reset.`,
      });
    }
  }

  return alerts;
}

export function mergeQuotaAlerts(prev: QuotaAlert[], next: QuotaAlert): QuotaAlert[] {
  if (prev.some((a) => a.service === next.service)) return prev;
  return [...prev, next];
}
