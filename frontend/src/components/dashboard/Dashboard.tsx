import { Card, CardHeader } from "../ui/Card";
import { Button } from "../ui/Button";
import { FileUploadZone } from "./FileUploadZone";
import { ProcessingPanel } from "./ProcessingPanel";
import { ResultsPanel } from "./ResultsPanel";
import { usePipeline } from "../../hooks/usePipeline";
import "./Dashboard.css";

export function Dashboard() {
  const pipeline = usePipeline();
  const isBusy = pipeline.phase === "uploading" || pipeline.phase === "processing";

  return (
    <div className="dashboard animate-fade-in">
      {pipeline.phase === "idle" || pipeline.phase === "error" ? (
        <Card padding="lg">
          <CardHeader
            title="Upload Order PDF"
            subtitle="Analyze Henry Schein orders and generate price match reports"
          />

          <FileUploadZone
            file={pipeline.selectedFile}
            onFileSelect={pipeline.selectFile}
            onClear={pipeline.clearFile}
            disabled={isBusy}
          />

          {pipeline.error && (
            <div className="dashboard__error" role="alert">
              {pipeline.error}
            </div>
          )}

          <Button
            fullWidth
            size="lg"
            disabled={!pipeline.selectedFile}
            onClick={pipeline.startProcessing}
            className="dashboard__submit"
          >
            Run Price Analysis
          </Button>
        </Card>
      ) : pipeline.phase === "complete" && pipeline.result ? (
        <Card padding="lg">
          <ResultsPanel
            uploadedFilename={pipeline.uploadedFilename}
            result={pipeline.result}
            onReset={pipeline.reset}
          />
        </Card>
      ) : (
        <Card padding="lg">
          <CardHeader
            title="Processing Order"
            subtitle={
              pipeline.uploadedFilename
                ? `Analyzing ${pipeline.uploadedFilename}`
                : "Running price intelligence pipeline"
            }
          />
          <ProcessingPanel
            progress={pipeline.progress}
            currentStep={pipeline.currentStep}
            statusLabel={pipeline.statusLabel}
            warnings={pipeline.warnings}
            logs={pipeline.logs}
          />
        </Card>
      )}
    </div>
  );
}
