import "./QuickGuidePanel.css";

const STEPS = [
  { num: 1, title: "Upload PDF", desc: "Henry Schein order confirmation", icon: "↑" },
  { num: 2, title: "AI + Search", desc: "Parse items & find prices", icon: "🔍" },
  { num: 3, title: "Match", desc: "Compare exact & alternate products", icon: "⚖" },
  { num: 4, title: "Download", desc: "3 Excel reports for your rep", icon: "↓" },
];

export function QuickGuidePanel() {
  return (
    <div className="quick-guide">
      <div className="quick-guide__header">
        <span className="quick-guide__badge">How it works</span>
        <h3 className="quick-guide__title">4-step price analysis</h3>
      </div>

      <div className="quick-guide__steps">
        {STEPS.map((step) => (
          <div key={step.num} className="quick-guide__step">
            <div className="quick-guide__step-icon">{step.icon}</div>
            <div className="quick-guide__step-body">
              <span className="quick-guide__step-num">Step {step.num}</span>
              <span className="quick-guide__step-title">{step.title}</span>
              <span className="quick-guide__step-desc">{step.desc}</span>
            </div>
          </div>
        ))}
      </div>

      <div className="quick-guide__footer">
        <p className="quick-guide__tip">
          Typical run time: <strong>2–5 min</strong> depending on line item count.
        </p>
      </div>
    </div>
  );
}
