import type { ProgressEvent } from "../types";
import { classifyError } from "../utils/errors";

const API_BASE = import.meta.env.VITE_API_URL ?? "/api";
const UPLOAD_TIMEOUT_MS = 60_000;
const FETCH_TIMEOUT_MS = 30_000;
const SSE_IDLE_TIMEOUT_MS = 10 * 60_000; // 10 min without events

export function getApiBase(): string {
  return API_BASE;
}

async function fetchWithTimeout(
  url: string,
  options: RequestInit = {},
  timeoutMs = FETCH_TIMEOUT_MS,
): Promise<Response> {
  const controller = new AbortController();
  const timer = window.setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await fetch(url, { ...options, signal: controller.signal });
  } catch (err) {
    if (err instanceof DOMException && err.name === "AbortError") {
      throw classifyError("Request timed out. Please try again.", "TIMEOUT");
    }
    throw classifyError(
      "Unable to reach the server. Check your network connection.",
      "NETWORK_ERROR",
    );
  } finally {
    window.clearTimeout(timer);
  }
}

async function parseApiError(res: Response): Promise<never> {
  const body = await res.json().catch(() => ({}));
  const detail = body.detail ?? body.message ?? `Server error (${res.status})`;
  const message = typeof detail === "string" ? detail : JSON.stringify(detail);
  throw classifyError(message, res.status >= 500 ? "API_ERROR" : "UPLOAD_FAILED");
}

export async function checkHealth(): Promise<{ status: string; version: string }> {
  const res = await fetchWithTimeout(`${API_BASE}/health`, {}, 10_000);
  if (!res.ok) throw classifyError("Backend unavailable", "NETWORK_ERROR");
  return res.json();
}

export function getDownloadUrl(filename: string): string {
  return `${API_BASE}/download/${encodeURIComponent(filename)}`;
}

export async function fetchOrderHistory(): Promise<import("../types").OrderRecord[]> {
  const res = await fetchWithTimeout(`${API_BASE}/history`);
  if (!res.ok) await parseApiError(res);
  return res.json();
}

export async function uploadPdf(file: File): Promise<{ job_id: string; filename: string }> {
  const form = new FormData();
  form.append("file", file);

  const res = await fetchWithTimeout(
    `${API_BASE}/upload`,
    { method: "POST", body: form },
    UPLOAD_TIMEOUT_MS,
  );
  if (!res.ok) await parseApiError(res);
  return res.json();
}

export interface JobErrorEvent {
  message: string;
  code?: string;
  order_id?: number;
}

export function subscribeToJob(
  jobId: string,
  handlers: {
    onProgress?: (data: ProgressEvent) => void;
    onLog?: (data: { level: string; message: string }) => void;
    onWarning?: (message: string) => void;
    onError?: (data: JobErrorEvent) => void;
    onComplete?: (result: Record<string, unknown>) => void;
    onConnectionError?: () => void;
    onTimeout?: () => void;
  },
): () => void {
  const es = new EventSource(`${API_BASE}/status/${jobId}`);
  let finished = false;
  let idleTimer: ReturnType<typeof setTimeout> | null = null;

  function resetIdleTimer() {
    if (idleTimer) clearTimeout(idleTimer);
    idleTimer = setTimeout(() => {
      if (!finished) {
        finished = true;
        es.close();
        handlers.onTimeout?.();
      }
    }, SSE_IDLE_TIMEOUT_MS);
  }

  resetIdleTimer();

  function finish() {
    finished = true;
    if (idleTimer) clearTimeout(idleTimer);
  }

  es.addEventListener("progress", (e) => {
    resetIdleTimer();
    handlers.onProgress?.(JSON.parse(e.data));
  });
  es.addEventListener("log", (e) => {
    resetIdleTimer();
    handlers.onLog?.(JSON.parse(e.data));
  });
  es.addEventListener("warning", (e) => {
    resetIdleTimer();
    const data = JSON.parse(e.data);
    handlers.onWarning?.(data.message);
  });
  es.addEventListener("error", (e) => {
    finish();
    const data = JSON.parse((e as MessageEvent).data);
    handlers.onError?.(data);
    es.close();
  });
  es.addEventListener("complete", (e) => {
    finish();
    handlers.onComplete?.(JSON.parse(e.data));
    es.close();
  });
  es.addEventListener("done", () => {
    finish();
    es.close();
  });
  es.onerror = () => {
    if (!finished) {
      finish();
      handlers.onConnectionError?.();
      es.close();
    }
  };

  return () => {
    finish();
    es.close();
  };
}
