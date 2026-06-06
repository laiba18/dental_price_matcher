import type { AppError } from "../../utils/errors";
import type { PipelineProgressState, PipelinePhase } from "../../types";
import { ErrorPanel } from "./ErrorPanel";
import { LoadingScreen } from "../ui/LoadingScreen";
import { ProcessingPanel } from "./ProcessingPanel";
import "./ProcessingStatus.css";

interface ProcessingStatusProps {
  phase: PipelinePhase;
  filename: string;
  progressState: PipelineProgressState;
  error?: AppError | null;
  onRetry?: () => void;
}

export function ProcessingStatus({
  phase,
  filename,
  progressState,
  error,
  onRetry,
}: ProcessingStatusProps) {
  const panelProps = {
    progress: progressState.progress,
    currentStep: progressState.currentStep,
    statusLabel: progressState.statusLabel,
    warnings: progressState.warnings,
    logs: progressState.logs,
    itemIndex: progressState.itemIndex,
    itemTotal: progressState.itemTotal,
    substep: progressState.substep,
    detail: progressState.detail,
    items: progressState.items,
    orderMeta: progressState.orderMeta,
    filename,
    isActive: phase === "processing",
  };

  if (phase === "error" && error) {
    return (
      <div className="processing-status processing-status--error">
        <ErrorPanel error={error} onRetry={onRetry} onDismiss={onRetry} />
        {progressState.logs.length > 0 && (
          <div className="processing-status__logs">
            <ProcessingPanel {...panelProps} isActive={false} />
          </div>
        )}
      </div>
    );
  }

  if (phase === "uploading") {
    return (
      <LoadingScreen
        title="Uploading your order"
        subtitle={`Sending ${filename} to the analysis server…`}
        progress={5}
      />
    );
  }

  return (
    <div className="processing-status" aria-live="polite" aria-busy="true">
      <ProcessingPanel {...panelProps} />
    </div>
  );
}
