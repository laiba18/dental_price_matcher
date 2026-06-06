import { useState } from "react";
import type { OrderRecord } from "../../types";
import { Card, CardHeader } from "../ui/Card";
import { Button } from "../ui/Button";
import { EmptyState } from "../ui/EmptyState";
import { Spinner } from "../ui/Spinner";
import { Alert } from "../ui/Alert";
import { StatusBadge } from "../ui/StatusBadge";
import { ReportDownloads } from "./ReportDownloads";
import "./PastOrdersList.css";

interface PastOrdersListProps {
  orders: OrderRecord[];
  isLoading: boolean;
  isRefreshing: boolean;
  error: string | null;
  onRefresh: () => void;
  highlightOrderId?: number | null;
}

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
      hour: "numeric",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

function formatMoney(value?: number | null): string {
  if (value == null) return "—";
  return `$${value.toLocaleString("en-US", { minimumFractionDigits: 2 })}`;
}

export function PastOrdersList({
  orders,
  isLoading,
  isRefreshing,
  error,
  onRefresh,
  highlightOrderId,
}: PastOrdersListProps) {
  const [expandedId, setExpandedId] = useState<number | null>(null);

  function toggleExpand(id: number) {
    setExpandedId((prev) => (prev === id ? null : id));
  }

  const failedCount = orders.filter((o) => o.status === "failed").length;

  return (
    <Card padding="md" className="past-orders">
      <CardHeader
        title="Past Orders"
        subtitle={
          failedCount > 0
            ? `${orders.length} orders · ${failedCount} failed — expand to see details`
            : "Previously analyzed orders and their generated reports"
        }
        action={
          <Button
            variant="ghost"
            size="sm"
            onClick={onRefresh}
            loading={isRefreshing}
            disabled={isLoading}
          >
            Refresh
          </Button>
        }
      />

      {error && (
        <Alert variant="error" title="Could not load orders">
          {error}
          <div className="past-orders__retry">
            <Button variant="secondary" size="sm" onClick={onRefresh}>
              Try again
            </Button>
          </div>
        </Alert>
      )}

      {isLoading && !error && (
        <div className="past-orders__loading">
          <Spinner label="Loading order history…" />
        </div>
      )}

      {!isLoading && !error && orders.length === 0 && (
        <EmptyState
          compact
          icon={
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
              <path
                d="M9 12h6M9 16h6M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8l-6-6z"
                stroke="currentColor"
                strokeWidth="1.5"
              />
            </svg>
          }
          title="No orders yet"
          description="Upload your first Henry Schein order PDF above to start generating price match reports."
        />
      )}

      {!isLoading && orders.length > 0 && (
        <div className="past-orders__list">
          {orders.map((order) => {
            const isFailed = order.status === "failed";
            const isExpanded = expandedId === order.id;
            const isHighlighted = highlightOrderId === order.id;
            const hasReports =
              order.status === "complete" &&
              (order.output_price_match || order.output_alternate || order.output_evidence);
            const isExpandable = hasReports || isFailed;

            return (
              <article
                key={order.id}
                className={`order-row ${isExpanded ? "order-row--expanded" : ""} ${
                  isHighlighted ? "order-row--highlight" : ""
                } ${isFailed ? "order-row--failed" : ""}`}
              >
                <button
                  type="button"
                  className="order-row__header"
                  onClick={() => isExpandable && toggleExpand(order.id)}
                  disabled={!isExpandable}
                  aria-expanded={isExpandable ? isExpanded : undefined}
                >
                  <div className="order-row__lead">
                    <div className="order-row__title-row">
                      <span className="order-row__filename">{order.filename}</span>
                      <StatusBadge status={order.status} />
                    </div>
                    <span className="order-row__processed">
                      {isFailed ? "Failed" : "Processed"} {formatDate(order.created_at)}
                    </span>
                  </div>

                  <div className="order-row__meta">
                    {order.order_ref && (
                      <span className="order-row__tag">Ref: {order.order_ref}</span>
                    )}
                    {order.order_date && (
                      <span className="order-row__tag">Date: {order.order_date}</span>
                    )}
                    {order.item_count != null && order.item_count > 0 && (
                      <span className="order-row__tag">{order.item_count} items</span>
                    )}
                    {order.total_price != null && (
                      <span className="order-row__tag">{formatMoney(order.total_price)}</span>
                    )}
                  </div>

                  {isExpandable && (
                    <div className="order-row__aside">
                      <span className={`order-row__chevron ${isExpanded ? "order-row__chevron--open" : ""}`}>
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
                          <path
                            d="M6 9l6 6 6-6"
                            stroke="currentColor"
                            strokeWidth="2"
                            strokeLinecap="round"
                            strokeLinejoin="round"
                          />
                        </svg>
                      </span>
                    </div>
                  )}
                </button>

                {isExpanded && hasReports && (
                  <div className="order-row__reports animate-fade-in">
                    <h4 className="order-row__reports-title">Generated Reports</h4>
                    <ReportDownloads source={order} compact />
                  </div>
                )}

                {isExpanded && isFailed && (
                  <div className="order-row__error animate-fade-in">
                    <h4 className="order-row__error-title">Failure Details</h4>
                    <p className="order-row__error-message">
                      {order.error_message ?? "Processing failed for an unknown reason."}
                    </p>
                    <p className="order-row__error-hint">
                      Upload the file again or verify it is a valid Henry Schein order PDF.
                    </p>
                  </div>
                )}
              </article>
            );
          })}
        </div>
      )}
    </Card>
  );
}
