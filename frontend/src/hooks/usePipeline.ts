import { useCallback, useRef, useState } from "react";
import { subscribeToJob, uploadPdf } from "../api/client";
import type { PipelinePhase, PipelineResult } from "../types";

export function usePipeline() {
  const [phase, setPhase] = useState<PipelinePhase>("idle");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [uploadedFilename, setUploadedFilename] = useState("");
  const [progress, setProgress] = useState(0);
  const [currentStep, setCurrentStep] = useState(0);
  const [statusLabel, setStatusLabel] = useState("");
  const [warnings, setWarnings] = useState<string[]>([]);
  const [logs, setLogs] = useState<string[]>([]);
  const [result, setResult] = useState<PipelineResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const unsubscribeRef = useRef<(() => void) | null>(null);

  const reset = useCallback(() => {
    unsubscribeRef.current?.();
    unsubscribeRef.current = null;
    setPhase("idle");
    setSelectedFile(null);
    setUploadedFilename("");
    setProgress(0);
    setCurrentStep(0);
    setStatusLabel("");
    setWarnings([]);
    setLogs([]);
    setResult(null);
    setError(null);
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
    setProgress(2);
    setStatusLabel("Uploading PDF...");
    setWarnings([]);
    setLogs([]);
    setError(null);
    setResult(null);

    try {
      const { job_id, filename } = await uploadPdf(selectedFile);
      setUploadedFilename(filename);
      setPhase("processing");
      setProgress(5);
      setStatusLabel("Starting pipeline...");
      setLogs(["Upload complete — starting analysis"]);

      unsubscribeRef.current?.();
      unsubscribeRef.current = subscribeToJob(job_id, {
        onProgress: (data) => {
          setProgress(data.pct);
          setCurrentStep(data.step);
          setStatusLabel(data.label);
          setLogs((prev) => [...prev, data.label]);
        },
        onWarning: (message) => {
          setWarnings((prev) => [...prev, message]);
          setLogs((prev) => [...prev, `⚠ ${message}`]);
        },
        onError: (message) => {
          setError(message);
          setPhase("error");
          setLogs((prev) => [...prev, `✖ ${message}`]);
        },
        onComplete: (data) => {
          setProgress(100);
          setResult(data as unknown as PipelineResult);
          setPhase("complete");
          setLogs((prev) => [...prev, "✔ Analysis complete"]);
        },
        onConnectionError: () => {
          setError("Lost connection to server. Please try again.");
          setPhase("error");
        },
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed");
      setPhase("error");
    }
  }, [selectedFile]);

  return {
    phase,
    selectedFile,
    uploadedFilename,
    progress,
    currentStep,
    statusLabel,
    warnings,
    logs,
    result,
    error,
    selectFile,
    clearFile,
    startProcessing,
    reset,
  };
}
