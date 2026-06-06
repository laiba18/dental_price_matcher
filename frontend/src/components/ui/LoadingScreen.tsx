import "./LoadingScreen.css";

interface LoadingScreenProps {
  title: string;
  subtitle?: string;
  progress?: number;
}

export function LoadingScreen({ title, subtitle, progress }: LoadingScreenProps) {
  return (
    <div className="loading-screen" role="status" aria-live="polite">
      <div className="loading-screen__orb" aria-hidden="true">
        <div className="loading-screen__ring loading-screen__ring--outer" />
        <div className="loading-screen__ring loading-screen__ring--inner" />
        <div className="loading-screen__core">
          <svg width="28" height="28" viewBox="0 0 24 24" fill="none">
            <path
              d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8l-6-6z"
              stroke="currentColor"
              strokeWidth="1.5"
            />
            <path d="M14 2v6h6" stroke="currentColor" strokeWidth="1.5" />
          </svg>
        </div>
      </div>

      <h3 className="loading-screen__title">{title}</h3>
      {subtitle && <p className="loading-screen__subtitle">{subtitle}</p>}

      {progress != null && (
        <div className="loading-screen__progress">
          <div className="loading-screen__bar">
            <div className="loading-screen__fill" style={{ width: `${progress}%` }} />
          </div>
          <span className="loading-screen__pct">{Math.round(progress)}%</span>
        </div>
      )}

      <div className="loading-screen__dots" aria-hidden="true">
        <span /><span /><span />
      </div>
    </div>
  );
}
