import { useEffect, useRef } from "react";
import { PIPELINE_MILESTONES, PIPELINE_STEPS, getStepProgress } from "../../constants/pipeline";
import { useSmoothProgress } from "../../hooks/useSmoothProgress";
import type { ItemProcessingState, OrderMeta, PipelineLogEntry, PipelineStep } from "../../types";
import { ProgressBar } from "../ui/ProgressBar";
import { CurrentActionPanel, ItemProgressBoard } from "./ItemProgressBoard";
import { OrderProcessingBanner } from "./OrderProcessingBanner";
import "./ProcessingPanel.css";

interface ProcessingPanelProps {
  progress: number;
  currentStep: number;
  statusLabel: string;
  warnings: string[];
  logs: PipelineLogEntry[];
  itemIndex?: number;
  itemTotal?: number;
  substep?: string;
  detail?: string;
  items?: ItemProcessingState[];
  orderMeta?: OrderMeta;
  filename?: string;
  isActive?: boolean;
  steps?: PipelineStep[];
}

function logLevelClass(level: PipelineLogEntry["level"]): string {
  switch (level) {
    case "error":
      return "activity-log__line--error";
    case "warn":
    case "warning":
      return "activity-log__line--warn";
    case "progress":
      return "activity-log__line--progress";
    default:
      return "activity-log__line--info";
  }
}

export function ProcessingPanel({
  progress,
  currentStep,
  statusLabel,
  warnings,
  logs,
  itemIndex,
  itemTotal,
  substep,
  detail,
  items = [],
  orderMeta,
  filename = "",
  isActive = true,
  steps = PIPELINE_STEPS,
}: ProcessingPanelProps) {
  const logRef = useRef<HTMLDivElement>(null);
  const smoothProgress = useSmoothProgress(progress, isActive);

  useEffect(() => {
    if (logRef.current) {
      logRef.current.scrollTop = logRef.current.scrollHeight;
    }
  }, [logs]);

  const doneCount = items.filter(
    (i) => i.substep === "done" || i.substep === "no_results",
  ).length;
  const activeItemIndex = itemIndex && itemIndex > 0 ? itemIndex : doneCount + 1;
  const itemBarPct =
    itemTotal && itemTotal > 0
      ? Math.min(100, Math.round(((doneCount + (itemIndex && itemIndex > 0 ? 0.35 : 0)) / itemTotal) * 100))
      : null;

  const showItemBoard = items.length > 0 && currentStep === 2;

  return (
    <div className="processing-panel animate-slide-up">
      <OrderProcessingBanner
        filename={filename}
        orderMeta={orderMeta}
        itemIndex={activeItemIndex}
        itemTotal={itemTotal}
        progress={smoothProgress}
      />

      <div className="processing-panel__header">
        <ProgressBar value={smoothProgress} label={statusLabel} animated />
        {itemTotal != null && itemTotal > 0 && (
          <div className="processing-panel__item-progress">
            <div className="processing-panel__item-label">
              <span>
                Line items: {doneCount} done · working on #{activeItemIndex} of {itemTotal}
              </span>
              <span>{itemBarPct ?? 0}%</span>
            </div>
            <ProgressBar value={itemBarPct ?? 0} showPercent={false} size="sm" animated />
          </div>
        )}
      </div>

      {(currentStep === 2 || substep) && (
        <CurrentActionPanel
          substep={substep}
          detail={detail}
          label={statusLabel}
          itemIndex={activeItemIndex}
          itemTotal={itemTotal}
        />
      )}

      {showItemBoard && (
        <ItemProgressBoard items={items} currentIndex={activeItemIndex} />
      )}

      <div className="processing-panel__milestones">
        <span className="processing-panel__milestones-title">Overall milestones</span>
        <div className="milestones">
          {PIPELINE_MILESTONES.map((m) => {
            const done = smoothProgress >= m.pct;
            const active = !done && smoothProgress >= m.pct - 8;
            return (
              <div
                key={m.pct}
                className={`milestone ${done ? "milestone--done" : ""} ${active ? "milestone--active" : ""}`}
              >
                <span className="milestone__pct">{m.pct}%</span>
                <span className="milestone__label">{m.label}</span>
              </div>
            );
          })}
        </div>
      </div>

      <div className="processing-panel__steps">
        {steps.map((step) => {
          const state =
            step.id < currentStep ? "done" : step.id === currentStep ? "active" : "pending";
          const stepPct = getStepProgress(step, smoothProgress);

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
                <div className="step-item__top">
                  <span className="step-item__name">{step.name}</span>
                  <span className="step-item__range">
                    {step.pctStart}–{step.pctEnd}%
                  </span>
                </div>
                <span className="step-item__desc">
                  {state === "active" ? statusLabel : step.description}
                </span>
                {state === "active" && (
                  <div className="step-item__sub-progress">
                    <ProgressBar value={stepPct} showPercent={false} size="sm" animated />
                  </div>
                )}
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
        <div className="activity-log">
          <div className="activity-log__header">
            <span>Live backend activity</span>
            <span className="activity-log__count">{logs.length} events</span>
          </div>
          <div className="activity-log__body activity-log__body--tall" ref={logRef} aria-live="polite">
            {logs.map((entry) => (
              <div key={entry.id} className={`activity-log__line ${logLevelClass(entry.level)}`}>
                {entry.pct != null && (
                  <span className="activity-log__pct">[{entry.pct}%]</span>
                )}
                <span>{entry.message}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
