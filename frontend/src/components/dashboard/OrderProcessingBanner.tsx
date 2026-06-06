import type { OrderMeta } from "../../types";
import "./OrderProcessingBanner.css";

interface OrderProcessingBannerProps {
  filename: string;
  orderMeta?: OrderMeta;
  itemIndex?: number;
  itemTotal?: number;
  progress: number;
}

export function OrderProcessingBanner({
  filename,
  orderMeta,
  itemIndex,
  itemTotal,
  progress,
}: OrderProcessingBannerProps) {
  const displayName = orderMeta?.filename || filename;
  const orderRef = orderMeta?.order_ref;
  const orderDate = orderMeta?.order_date;

  return (
    <div className="order-banner">
      <div className="order-banner__pulse" aria-hidden="true" />
      <div className="order-banner__content">
        <div className="order-banner__top">
          <span className="order-banner__badge">Processing Order</span>
          {orderMeta?.order_id != null && (
            <span className="order-banner__id">#{orderMeta.order_id}</span>
          )}
        </div>

        <h3 className="order-banner__filename">{displayName}</h3>

        <div className="order-banner__meta">
          {orderRef && <span>Ref: {orderRef}</span>}
          {orderDate && <span>Date: {orderDate}</span>}
          {itemTotal != null && itemTotal > 0 && (
            <span>
              {itemIndex != null && itemIndex > 0
                ? `Item ${itemIndex} of ${itemTotal}`
                : `${itemTotal} line items`}
            </span>
          )}
          <span className="order-banner__pct">{Math.round(progress)}% overall</span>
        </div>
      </div>
    </div>
  );
}
