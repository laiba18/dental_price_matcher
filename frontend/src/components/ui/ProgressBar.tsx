import "./ProgressBar.css";

interface ProgressBarProps {
  value: number;
  label?: string;
  showPercent?: boolean;
  animated?: boolean;
  size?: "sm" | "md";
}

export function ProgressBar({
  value,
  label,
  showPercent = true,
  animated = true,
  size = "md",
}: ProgressBarProps) {
  const clamped = Math.min(100, Math.max(0, value));

  return (
    <div className="progress-bar">
      {(label || showPercent) && (
        <div className="progress-bar__header">
          {label && <span className="progress-bar__label">{label}</span>}
          {showPercent && (
            <span className="progress-bar__percent">{Math.round(clamped)}%</span>
          )}
        </div>
      )}
      <div className={`progress-bar__track progress-bar__track--${size}`}>
        <div
          className={`progress-bar__fill ${animated ? "progress-bar__fill--animated" : ""}`}
          style={{ width: `${clamped}%` }}
          role="progressbar"
          aria-valuenow={clamped}
          aria-valuemin={0}
          aria-valuemax={100}
        />
      </div>
    </div>
  );
}
