import { REPORT_DEFINITIONS, getOrderReportFilename, getReportFilename } from "../../constants/reports";
import { getDownloadUrl } from "../../api/client";
import type { OrderRecord, PipelineResult } from "../../types";
import "./ReportDownloads.css";

interface ReportDownloadsProps {
  source: PipelineResult | OrderRecord;
  compact?: boolean;
}

function resolveFilename(source: PipelineResult | OrderRecord, id: string): string {
  if ("output_price_match" in source && "line_items" in source) {
    return getReportFilename(source as PipelineResult, id);
  }
  return getOrderReportFilename(source as OrderRecord, id);
}

export function ReportDownloads({ source, compact = false }: ReportDownloadsProps) {
  const available = REPORT_DEFINITIONS.filter((def) => {
    const filename = resolveFilename(source, def.id);
    return filename.length > 0;
  });

  if (available.length === 0) {
    return (
      <p className="report-downloads__none">
        No reports available for this order yet.
      </p>
    );
  }

  return (
    <div className={`report-downloads ${compact ? "report-downloads--compact" : ""}`}>
      {available.map((file) => {
        const filename = resolveFilename(source, file.id);
        const url = getDownloadUrl(filename);

        return (
          <div key={file.id} className={`report-downloads__row report-downloads__row--${file.variant}`}>
            <div className="report-downloads__icon" aria-hidden="true">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
                <path
                  d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8l-6-6z"
                  stroke="currentColor"
                  strokeWidth="1.5"
                />
                <path d="M14 2v6h6" stroke="currentColor" strokeWidth="1.5" />
              </svg>
            </div>
            <div className="report-downloads__body">
              <span className="report-downloads__name">{file.label}</span>
              {!compact && (
                <span className="report-downloads__desc">{file.description}</span>
              )}
              <span className="report-downloads__filename">{filename}</span>
            </div>
            <a
              href={url}
              download={filename}
              className="report-downloads__btn"
              target="_blank"
              rel="noopener noreferrer"
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
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
  );
}
