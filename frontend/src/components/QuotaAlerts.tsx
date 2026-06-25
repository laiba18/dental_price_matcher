import type { QuotaAlert } from "../types";

const SERVICE_LABELS: Record<string, string> = {
  groq: "Groq",
  gemini: "Gemini",
  firecrawl: "Firecrawl",
  serpapi: "SerpAPI",
  openai: "OpenAI",
  openrouter: "OpenRouter",
};

interface QuotaAlertsProps {
  alerts: QuotaAlert[];
}

export function QuotaAlerts({ alerts }: QuotaAlertsProps) {
  if (alerts.length === 0) return null;

  return (
    <div className="quota-alerts" role="alert">
      <div className="quota-alerts__header">
        <span className="quota-alerts__icon" aria-hidden>
          ⚠
        </span>
        <div>
          <strong>API credit limits reached</strong>
          <p>Some services ran out of quota during this run. Reports may be less complete.</p>
        </div>
      </div>
      <ul className="quota-alerts__list">
        {alerts.map((alert) => (
          <li key={alert.service} className="quota-alerts__item">
            <span className="quota-alerts__service">
              {SERVICE_LABELS[alert.service] ?? alert.service}
            </span>
            <span className="quota-alerts__message">{alert.message}</span>
            {alert.detail && <span className="quota-alerts__detail">{alert.detail}</span>}
          </li>
        ))}
      </ul>
    </div>
  );
}
