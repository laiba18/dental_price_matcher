import type { OrderStatus } from "../../types";
import "./StatusBadge.css";

interface StatusBadgeProps {
  status: OrderStatus | string;
}

const LABELS: Record<string, string> = {
  complete: "Complete",
  processing: "Processing",
  pending: "Pending",
  failed: "Failed",
};

export function StatusBadge({ status }: StatusBadgeProps) {
  const normalized = status.toLowerCase();
  const label = LABELS[normalized] ?? status;

  return (
    <span className={`status-badge status-badge--${normalized}`}>
      <span className="status-badge__dot" aria-hidden="true" />
      {label}
    </span>
  );
}
