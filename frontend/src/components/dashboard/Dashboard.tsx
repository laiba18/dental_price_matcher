import { useCallback, useState } from "react";
import { Card, CardHeader } from "../ui/Card";
import { DashboardHero } from "./DashboardHero";
import { UploadSection } from "./UploadSection";
import { QuickGuidePanel } from "./QuickGuidePanel";
import { ProcessingStatus } from "./ProcessingStatus";
import { ResultsPanel } from "./ResultsPanel";
import { PastOrdersList } from "./PastOrdersList";
import { usePipeline } from "../../hooks/usePipeline";
import { useOrderHistory } from "../../hooks/useOrderHistory";
import { useToast } from "../../context/ToastContext";
import type { AppError } from "../../utils/errors";
import type { PipelineResult } from "../../types";
import "./Dashboard.css";

export function Dashboard() {
  const history = useOrderHistory();
  const toast = useToast();
  const [highlightOrderId, setHighlightOrderId] = useState<number | null>(null);
  const [uploadError, setUploadError] = useState<AppError | null>(null);

  const onComplete = useCallback(
    (result: PipelineResult) => {
      history.refresh();
      toast.success(
        "Analysis complete",
        `${result.line_items} items processed · Reports ready to download`,
      );
    },
    [history.refresh, toast],
  );

  const onError = useCallback(
    (error: AppError, orderId?: number) => {
      history.refresh();
      if (orderId) setHighlightOrderId(orderId);
      toast.error(error.title, error.message);
    },
    [history.refresh, toast],
  );

  const pipeline = usePipeline({ onComplete, onError });

  const isProcessing =
    pipeline.phase === "uploading" || pipeline.phase === "processing";
  const isComplete = pipeline.phase === "complete" && pipeline.result;
  const showUpload = pipeline.phase === "idle" || pipeline.phase === "error";
  const showIdleGrid = showUpload && !isProcessing && pipeline.phase !== "error";

  const handleReset = () => {
    if (pipeline.result?.order_id) {
      setHighlightOrderId(pipeline.result.order_id);
    } else if (pipeline.failedOrderId) {
      setHighlightOrderId(pipeline.failedOrderId);
    }
    setUploadError(null);
    pipeline.reset();
  };

  const handleValidationError = useCallback(
    (error: AppError) => {
      setUploadError(error);
      toast.error(error.title, error.message);
    },
    [toast],
  );

  return (
    <div className="dashboard">
      <DashboardHero orders={history.orders} isLoading={history.isLoading} />

      <section className="dashboard__workspace">
        {showIdleGrid && (
          <div className="dashboard__split">
            <UploadSection
              selectedFile={pipeline.selectedFile}
              onFileSelect={(file) => {
                setUploadError(null);
                pipeline.selectFile(file);
              }}
              onClear={pipeline.clearFile}
              onSubmit={pipeline.startProcessing}
              onValidationError={handleValidationError}
              disabled={isProcessing}
              loading={pipeline.phase === "uploading"}
              error={uploadError ?? (pipeline.phase === "idle" ? pipeline.error : null)}
            />
            <QuickGuidePanel />
          </div>
        )}

        {showUpload && pipeline.phase === "error" && (
          <div className="dashboard__split dashboard__split--error">
            <UploadSection
              selectedFile={pipeline.selectedFile}
              onFileSelect={(file) => {
                setUploadError(null);
                pipeline.selectFile(file);
              }}
              onClear={pipeline.clearFile}
              onSubmit={pipeline.startProcessing}
              onValidationError={handleValidationError}
              disabled={isProcessing}
              loading={false}
              error={uploadError ?? pipeline.error}
            />
          </div>
        )}

        {isProcessing && (
          <Card padding="md" className="dashboard__panel dashboard__panel--active">
            <CardHeader
              title="Processing Order"
              subtitle={pipeline.uploadedFilename || pipeline.selectedFile?.name || ""}
            />
            <ProcessingStatus
              phase={pipeline.phase}
              filename={pipeline.uploadedFilename || pipeline.selectedFile?.name || ""}
              progressState={pipeline.progressState}
              error={pipeline.error}
              onRetry={handleReset}
            />
          </Card>
        )}

        {pipeline.phase === "error" && pipeline.error && (
          <Card padding="md" className="dashboard__panel dashboard__panel--error">
            <CardHeader title="Analysis Failed" subtitle={pipeline.uploadedFilename} />
            <ProcessingStatus
              phase={pipeline.phase}
              filename={pipeline.uploadedFilename || ""}
              progressState={pipeline.progressState}
              error={pipeline.error}
              onRetry={handleReset}
            />
          </Card>
        )}

        {isComplete && pipeline.result && (
          <Card padding="md" className="dashboard__panel dashboard__panel--results">
            <ResultsPanel
              uploadedFilename={pipeline.uploadedFilename}
              result={pipeline.result}
              onReset={handleReset}
            />
          </Card>
        )}
      </section>

      <PastOrdersList
        orders={history.orders}
        isLoading={history.isLoading}
        isRefreshing={history.isRefreshing}
        error={history.error}
        onRefresh={history.refresh}
        highlightOrderId={highlightOrderId ?? pipeline.failedOrderId}
      />
    </div>
  );
}
