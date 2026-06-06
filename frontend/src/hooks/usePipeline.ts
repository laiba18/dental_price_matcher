import { useCallback, useRef, useState } from "react";
import { subscribeToJob, uploadPdf } from "../api/client";
import { updateItemStates } from "../utils/itemProgress";
import { classifyError, type AppError } from "../utils/errors";
import type {
  LogLevel,
  PipelineLogEntry,
  PipelinePhase,
  PipelineProgressState,
  PipelineResult,
} from "../types";

interface UsePipelineOptions {
  onComplete?: (result: PipelineResult) => void;
  onError?: (error: AppError, orderId?: number) => void;
}

const INITIAL_PROGRESS: PipelineProgressState = {
  progress: 0,
  currentStep: 0,
  statusLabel: "",
  warnings: [],
  logs: [],
  items: [],
};

let logCounter = 0;

function makeLog(level: LogLevel, message: string, pct?: number): PipelineLogEntry {
  logCounter += 1;
  return {
    id: `log-${logCounter}`,
    ts: Date.now(),
    level,
    message,
    pct,
  };
}

function appendLog(prev: PipelineLogEntry[], entry: PipelineLogEntry): PipelineLogEntry[] {
  const next = [...prev, entry];
  return next.length > 200 ? next.slice(-200) : next;
}

export function usePipeline(options: UsePipelineOptions = {}) {
  const { onComplete, onError } = options;
  const onCompleteRef = useRef(onComplete);
  const onErrorRef = useRef(onError);
  onCompleteRef.current = onComplete;
  onErrorRef.current = onError;

  const [phase, setPhase] = useState<PipelinePhase>("idle");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [uploadedFilename, setUploadedFilename] = useState("");
  const [progressState, setProgressState] = useState<PipelineProgressState>(INITIAL_PROGRESS);
  const [result, setResult] = useState<PipelineResult | null>(null);
  const [error, setError] = useState<AppError | null>(null);
  const [failedOrderId, setFailedOrderId] = useState<number | null>(null);
  const unsubscribeRef = useRef<(() => void) | null>(null);

  const handleFailure = useCallback((appError: AppError, orderId?: number) => {
    setError(appError);
    setPhase("error");
    if (orderId) setFailedOrderId(orderId);
    onErrorRef.current?.(appError, orderId);
  }, []);

  const reset = useCallback(() => {
    unsubscribeRef.current?.();
    unsubscribeRef.current = null;
    setPhase("idle");
    setSelectedFile(null);
    setUploadedFilename("");
    setProgressState(INITIAL_PROGRESS);
    setResult(null);
    setError(null);
    setFailedOrderId(null);
  }, []);

  const selectFile = useCallback((file: File) => {
    setSelectedFile(file);
    setError(null);
  }, []);

  const clearFile = useCallback(() => {
    setSelectedFile(null);
  }, []);

  const startProcessing = useCallback(async () => {
    if (!selectedFile) return;

    setPhase("uploading");
    setProgressState({
      progress: 2,
      currentStep: 0,
      statusLabel: "Uploading PDF…",
      warnings: [],
      logs: [makeLog("progress", "Uploading PDF to server…", 2)],
      items: [],
    });
    setError(null);
    setResult(null);
    setFailedOrderId(null);

    try {
      const { job_id, filename } = await uploadPdf(selectedFile);
      setUploadedFilename(filename);
      setPhase("processing");
      setProgressState((prev) => ({
        ...prev,
        progress: 5,
        statusLabel: "Starting analysis…",
        logs: appendLog(prev.logs, makeLog("progress", "Upload complete — starting analysis", 5)),
      }));

      unsubscribeRef.current?.();
      unsubscribeRef.current = subscribeToJob(job_id, {
        onProgress: (data) => {
          setProgressState((prev) => ({
            ...prev,
            progress: data.pct,
            currentStep: data.step,
            statusLabel: data.label,
            itemIndex: data.item_index,
            itemTotal: data.item_total,
            substep: data.substep,
            detail: data.detail,
            items: updateItemStates(prev.items, data),
            orderMeta: {
              filename: data.filename ?? prev.orderMeta?.filename,
              order_ref: data.order_ref ?? prev.orderMeta?.order_ref,
              order_id: data.order_id ?? prev.orderMeta?.order_id,
              order_date: data.order_date ?? prev.orderMeta?.order_date,
            },
            logs: appendLog(
              prev.logs,
              makeLog("progress", `[${data.pct}%] ${data.label}`, data.pct),
            ),
          }));
        },
        onLog: (data) => {
          const level = (data.level === "warn" ? "warn" : data.level) as LogLevel;
          setProgressState((prev) => ({
            ...prev,
            logs: appendLog(prev.logs, makeLog(level, data.message)),
          }));
        },
        onWarning: (message) => {
          setProgressState((prev) => ({
            ...prev,
            warnings: [...prev.warnings, message],
            logs: appendLog(prev.logs, makeLog("warning", message)),
          }));
        },
        onError: (data) => {
          const appError = classifyError(data.message, data.code);
          setProgressState((prev) => ({
            ...prev,
            logs: appendLog(prev.logs, makeLog("error", data.message)),
          }));
          handleFailure(appError, data.order_id);
        },
        onComplete: (data) => {
          const pipelineResult = data as unknown as PipelineResult;
          setProgressState((prev) => ({
            ...prev,
            progress: 100,
            currentStep: 4,
            statusLabel: "Analysis complete",
            logs: appendLog(prev.logs, makeLog("progress", "✔ Analysis complete — reports ready", 100)),
          }));
          setResult(pipelineResult);
          setPhase("complete");
          onCompleteRef.current?.(pipelineResult);
        },
        onConnectionError: () => {
          handleFailure(
            classifyError(
              "Lost connection to the server during processing.",
              "CONNECTION_LOST",
            ),
          );
        },
        onTimeout: () => {
          handleFailure(
            classifyError(
              "Processing timed out — no updates received for 10 minutes.",
              "TIMEOUT",
            ),
          );
        },
      });
    } catch (err) {
      const appError =
        err && typeof err === "object" && "title" in err
          ? (err as AppError)
          : classifyError(err instanceof Error ? err.message : "Upload failed", "UPLOAD_FAILED");
      handleFailure(appError);
    }
  }, [selectedFile, handleFailure]);

  return {
    phase,
    selectedFile,
    uploadedFilename,
    progress: progressState.progress,
    currentStep: progressState.currentStep,
    statusLabel: progressState.statusLabel,
    warnings: progressState.warnings,
    logs: progressState.logs,
    progressState,
    result,
    error,
    failedOrderId,
    selectFile,
    clearFile,
    startProcessing,
    reset,
    isBusy: phase === "uploading" || phase === "processing",
  };
}
