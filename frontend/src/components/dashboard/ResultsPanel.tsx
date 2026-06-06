import type { PipelineResult } from "../../types";
import { Button } from "../ui/Button";
import { ReportDownloads } from "./ReportDownloads";
import "./ResultsPanel.css";

interface ResultsPanelProps {
  uploadedFilename: string;
  result: PipelineResult;
  onReset: () => void;
}

export function ResultsPanel({ uploadedFilename, result, onReset }: ResultsPanelProps) {
  const savings = result.total_potential_savings ?? 0;

  return (
    <div className="results-panel animate-slide-up">
      <div className="results-panel__success-banner">
        <div className="results-panel__success-icon" aria-hidden="true">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
            <path
              d="M20 6L9 17l-5-5"
              stroke="currentColor"
              strokeWidth="2.5"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </div>
        <div>
          <h3 className="results-panel__success-title">Analysis complete</h3>
          <p className="results-panel__success-sub">Your reports are ready to download</p>
        </div>
      </div>

      <div className="results-panel__file-row">
        <div className="results-panel__file-info">
          <span className="results-panel__file-label">Uploaded file</span>
          <span className="results-panel__file-name">{uploadedFilename}</span>
        </div>
        <span className="results-panel__file-badge">Processed</span>
      </div>

      <div className="results-panel__metrics">
        <Metric label="Line Items" value={String(result.line_items)} />
        <Metric label="Exact Matches" value={String(result.exact_matches)} />
        <Metric label="Equiv. Recs" value={String(result.equiv_recommendations)} />
        <Metric
          label="Potential Savings"
          value={`$${savings.toLocaleString("en-US", { minimumFractionDigits: 2 })}`}
          highlight
        />
      </div>

      {(result.order_ref || result.order_date) && (
        <div className="results-panel__meta">
          {result.order_ref && (
            <div>
              <span>Order Ref</span>
              <strong>{result.order_ref}</strong>
            </div>
          )}
          {result.order_date && (
            <div>
              <span>Order Date</span>
              <strong>{result.order_date}</strong>
            </div>
          )}
        </div>
      )}

      <div className="results-panel__downloads">
        <h4 className="results-panel__downloads-title">Download Reports</h4>
        <ReportDownloads source={result} />
      </div>

      <Button variant="secondary" fullWidth onClick={onReset}>
        Process another order
      </Button>
    </div>
  );
}

function Metric({
  label,
  value,
  highlight = false,
}: {
  label: string;
  value: string;
  highlight?: boolean;
}) {
  return (
    <div className={`metric-card ${highlight ? "metric-card--highlight" : ""}`}>
      <span className="metric-card__label">{label}</span>
      <span className="metric-card__value">{value}</span>
    </div>
  );
}
