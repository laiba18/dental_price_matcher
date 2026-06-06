import type { OrderRecord } from "../../types";
import "./DashboardHero.css";

interface DashboardHeroProps {
  orders: OrderRecord[];
  isLoading?: boolean;
}

export function DashboardHero({ orders, isLoading }: DashboardHeroProps) {
  const total = orders.length;
  const completed = orders.filter((o) => o.status === "complete").length;
  const failed = orders.filter((o) => o.status === "failed").length;
  const totalItems = orders.reduce((sum, o) => sum + (o.item_count ?? 0), 0);
  const totalSpend = orders.reduce((sum, o) => sum + (o.total_price ?? 0), 0);

  const stats = [
    { label: "Orders", value: isLoading ? "—" : String(total), icon: "📋" },
    { label: "Completed", value: isLoading ? "—" : String(completed), icon: "✓", accent: "success" as const },
    { label: "Failed", value: isLoading ? "—" : String(failed), icon: "!", accent: failed > 0 ? "error" as const : undefined },
    { label: "Line Items", value: isLoading ? "—" : String(totalItems), icon: "📦" },
    {
      label: "Order Value",
      value: isLoading ? "—" : totalSpend > 0 ? `$${totalSpend.toLocaleString("en-US", { minimumFractionDigits: 0 })}` : "—",
      icon: "💰",
      accent: "gold" as const,
    },
  ];

  return (
    <section className="dashboard-hero">
      <div className="dashboard-hero__glow" aria-hidden="true" />
      <div className="dashboard-hero__text">
        <span className="dashboard-hero__eyebrow">Supply Intelligence</span>
        <h1 className="dashboard-hero__title">Dashboard</h1>
        <p className="dashboard-hero__subtitle">
          Upload Henry Schein orders, compare supplier prices, and download savings reports in minutes.
        </p>
      </div>
      <div className="dashboard-hero__stats">
        {stats.map((s) => (
          <div
            key={s.label}
            className={`dashboard-hero__stat ${s.accent ? `dashboard-hero__stat--${s.accent}` : ""}`}
          >
            <span className="dashboard-hero__stat-icon" aria-hidden="true">{s.icon}</span>
            <div className="dashboard-hero__stat-body">
              <span className="dashboard-hero__stat-value">{s.value}</span>
              <span className="dashboard-hero__stat-label">{s.label}</span>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
