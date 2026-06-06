import type { AppError } from "../../utils/errors";
import { Button } from "../ui/Button";
import "./ErrorPanel.css";

interface ErrorPanelProps {
  error: AppError;
  onRetry?: () => void;
  onDismiss?: () => void;
}

export function ErrorPanel({ error, onRetry, onDismiss }: ErrorPanelProps) {
  return (
    <div className="error-panel animate-shake-in">
      <div className="error-panel__glow" aria-hidden="true" />
      <div className="error-panel__icon" aria-hidden="true">
        <svg width="32" height="32" viewBox="0 0 24 24" fill="none">
          <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="1.5" />
          <path d="M12 7v6M12 17h.01" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" />
        </svg>
      </div>

      <h3 className="error-panel__title">{error.title}</h3>
      <p className="error-panel__message">{error.message}</p>

      <div className="error-panel__suggestion">
        <span className="error-panel__suggestion-label">What you can do</span>
        <p>{error.suggestion}</p>
      </div>

      <div className="error-panel__actions">
        {onRetry && (
          <Button variant="primary" onClick={onRetry}>
            Try again
          </Button>
        )}
        {onDismiss && (
          <Button variant="secondary" onClick={onDismiss}>
            Dismiss
          </Button>
        )}
      </div>

      <span className="error-panel__code">Error code: {error.code}</span>
    </div>
  );
}
