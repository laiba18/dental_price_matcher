import { ReactNode } from "react";
import "./Alert.css";

type AlertVariant = "error" | "warning" | "info" | "success";

interface AlertProps {
  variant?: AlertVariant;
  title?: string;
  children: ReactNode;
  onDismiss?: () => void;
}

export function Alert({ variant = "info", title, children, onDismiss }: AlertProps) {
  return (
    <div className={`alert alert--${variant}`} role="alert">
      <div className="alert__body">
        {title && <p className="alert__title">{title}</p>}
        <div className="alert__content">{children}</div>
      </div>
      {onDismiss && (
        <button type="button" className="alert__dismiss" onClick={onDismiss} aria-label="Dismiss">
          ×
        </button>
      )}
    </div>
  );
}
