import { PipelineStep } from "../../types";
import { ProgressBar } from "../ui/ProgressBar";
import "./ProcessingPanel.css";

const STEPS: PipelineStep[] = [
  { id: 1, name: "PDF Extraction", description: "Reading line items from order PDF" },
  { id: 2, name: "Intelligence", description: "Parsing descriptions & searching prices" },
  { id: 3, name: "Matching", description: "Scoring matches & equivalencies" },
  { id: 4, name: "Reports", description: "Generating Excel output files" },
];

interface ProcessingPanelProps {
  progress: number;
  currentStep: number;
  statusLabel: string;
  warnings: string[];
  logs: string[];
}

export function ProcessingPanel({
  progress,
  currentStep,
  statusLabel,
  warnings,
  logs,
}: ProcessingPanelProps) {
  return (
    <div className="processing-panel animate-slide-up">
      <ProgressBar value={progress} label={statusLabel} />

      <div className="processing-panel__steps">
        {STEPS.map((step) => {
          const state =
            step.id < currentStep
              ? "done"
              : step.id === currentStep
                ? "active"
                : "pending";

          return (
            <div key={step.id} className={`step-item step-item--${state}`}>
              <div className="step-item__indicator">
                {state === "done" ? (
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
                    <path
                      d="M20 6L9 17l-5-5"
                      stroke="currentColor"
                      strokeWidth="2.5"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    />
                  </svg>
                ) : (
                  step.id
                )}
              </div>
              <div className="step-item__body">
                <span className="step-item__name">{step.name}</span>
                <span className="step-item__desc">
                  {state === "active" ? statusLabel : step.description}
                </span>
              </div>
              {state === "active" && <span className="step-item__pulse" aria-hidden="true" />}
            </div>
          );
        })}
      </div>

      {warnings.length > 0 && (
        <div className="processing-panel__warnings">
          {warnings.map((w, i) => (
            <p key={i}>⚠ {w}</p>
          ))}
        </div>
      )}

      {logs.length > 0 && (
        <div className="processing-panel__log" aria-live="polite">
          {logs.slice(-6).map((line, i) => (
            <div key={i} className="processing-panel__log-line">
              › {line}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
