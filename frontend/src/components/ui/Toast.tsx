import { useToast, type Toast, type ToastVariant } from "../../context/ToastContext";
import "./Toast.css";

const ICONS: Record<ToastVariant, string> = {
  success: "✓",
  error: "✕",
  warning: "⚠",
  info: "ℹ",
};

function ToastItem({ toast, onDismiss }: { toast: Toast; onDismiss: () => void }) {
  return (
    <div
      className={`toast toast--${toast.variant} animate-toast-in`}
      role="alert"
      aria-live="assertive"
    >
      <span className="toast__icon" aria-hidden="true">
        {ICONS[toast.variant]}
      </span>
      <div className="toast__body">
        <p className="toast__title">{toast.title}</p>
        {toast.message && <p className="toast__message">{toast.message}</p>}
      </div>
      <button type="button" className="toast__close" onClick={onDismiss} aria-label="Dismiss">
        ×
      </button>
    </div>
  );
}

export function ToastContainer() {
  const { toasts, dismissToast } = useToast();

  if (toasts.length === 0) return null;

  return (
    <div className="toast-container" aria-label="Notifications">
      {toasts.map((t) => (
        <ToastItem key={t.id} toast={t} onDismiss={() => dismissToast(t.id)} />
      ))}
    </div>
  );
}
