import type { OrderRecord } from "../../types";
import "./DashboardStats.css";

interface DashboardStatsProps {
  orders: OrderRecord[];
  isLoading?: boolean;
}

export function DashboardStats({ orders, isLoading }: DashboardStatsProps) {
  const total = orders.length;
  const completed = orders.filter((o) => o.status === "complete").length;
  const failed = orders.filter((o) => o.status === "failed").length;
  const totalItems = orders.reduce((sum, o) => sum + (o.item_count ?? 0), 0);
  const totalSpend = orders.reduce((sum, o) => sum + (o.total_price ?? 0), 0);

  const stats = [
    { label: "Total Orders", value: isLoading ? "—" : String(total), variant: "default" as const },
    { label: "Completed", value: isLoading ? "—" : String(completed), variant: "success" as const },
    { label: "Failed", value: isLoading ? "—" : String(failed), variant: failed > 0 ? "error" as const : "default" as const },
    {
      label: "Line Items",
      value: isLoading ? "—" : String(totalItems),
      variant: "default" as const,
    },
    {
      label: "Order Value",
      value: isLoading
        ? "—"
        : totalSpend > 0
          ? `$${totalSpend.toLocaleString("en-US", { minimumFractionDigits: 2 })}`
          : "—",
      variant: "default" as const,
    },
  ];

  return (
    <div className="dashboard-stats">
      {stats.map((stat) => (
        <div key={stat.label} className={`dashboard-stats__card dashboard-stats__card--${stat.variant}`}>
          <span className="dashboard-stats__label">{stat.label}</span>
          <span className="dashboard-stats__value">{stat.value}</span>
        </div>
      ))}
    </div>
  );
}
