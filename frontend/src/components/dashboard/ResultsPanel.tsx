import { PipelineResult, OutputFile } from "../../types";
import { getDownloadUrl } from "../../api/client";
import { Button } from "../ui/Button";
import "./ResultsPanel.css";

interface ResultsPanelProps {
  uploadedFilename: string;
  result: PipelineResult;
  onReset: () => void;
}

const OUTPUT_FILES: Omit<OutputFile, "filename">[] = [
  {
    id: "price_match",
    label: "Price Match Report",
    description: "Exact matches sorted by savings — hand to your rep",
    variant: "primary",
  },
  {
    id: "alternate",
    label: "Alternate Purchase List",
    description: "Equivalency-driven items to buy direct",
    variant: "secondary",
  },
  {
    id: "evidence",
    label: "Background Evidence",
    description: "All prices, URLs, and match confidence data",
    variant: "neutral",
  },
];

function getFilename(result: PipelineResult, id: string): string {
  switch (id) {
    case "price_match":
      return result.output_price_match;
    case "alternate":
      return result.output_alternate;
    case "evidence":
      return result.output_evidence;
    default:
      return "";
  }
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
        {OUTPUT_FILES.map((file) => {
          const filename = getFilename(result, file.id);
          const url = getDownloadUrl(filename);

          return (
            <div key={file.id} className={`download-row download-row--${file.variant}`}>
              <div className="download-row__icon" aria-hidden="true">
                <svg width="22" height="22" viewBox="0 0 24 24" fill="none">
                  <path
                    d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8l-6-6z"
                    stroke="currentColor"
                    strokeWidth="1.5"
                  />
                  <path d="M14 2v6h6" stroke="currentColor" strokeWidth="1.5" />
                </svg>
              </div>
              <div className="download-row__body">
                <span className="download-row__name">{file.label}</span>
                <span className="download-row__desc">{file.description}</span>
                <span className="download-row__filename">{filename}</span>
              </div>
              <a
                href={url}
                download={filename}
                className="download-row__btn"
                target="_blank"
                rel="noopener noreferrer"
              >
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
                  <path
                    d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M7 10l5 5 5-5M12 15V3"
                    stroke="currentColor"
                    strokeWidth="2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                </svg>
                Download
              </a>
            </div>
          );
        })}
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
