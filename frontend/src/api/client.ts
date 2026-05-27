const API_BASE = import.meta.env.VITE_API_URL ?? "/api";

export function getApiBase(): string {
  return API_BASE;
}

export async function checkHealth(): Promise<{ status: string; version: string }> {
  const res = await fetch(`${API_BASE}/health`);
  if (!res.ok) throw new Error("Backend unavailable");
  return res.json();
}

export function getDownloadUrl(filename: string): string {
  return `${API_BASE}/download/${encodeURIComponent(filename)}`;
}

export async function uploadPdf(file: File): Promise<{ job_id: string; filename: string }> {
  const form = new FormData();
  form.append("file", file);

  const res = await fetch(`${API_BASE}/upload`, { method: "POST", body: form });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail ?? "Upload failed");
  }
  return res.json();
}

export function subscribeToJob(
  jobId: string,
  handlers: {
    onProgress?: (data: { step: number; pct: number; label: string }) => void;
    onWarning?: (message: string) => void;
    onError?: (message: string) => void;
    onComplete?: (result: Record<string, unknown>) => void;
    onConnectionError?: () => void;
  },
): () => void {
  const es = new EventSource(`${API_BASE}/status/${jobId}`);

  es.addEventListener("progress", (e) => {
    handlers.onProgress?.(JSON.parse(e.data));
  });
  es.addEventListener("warning", (e) => {
    const data = JSON.parse(e.data);
    handlers.onWarning?.(data.message);
  });
  es.addEventListener("error", (e) => {
    const data = JSON.parse((e as MessageEvent).data);
    handlers.onError?.(data.message);
    es.close();
  });
  es.addEventListener("complete", (e) => {
    handlers.onComplete?.(JSON.parse(e.data));
    es.close();
  });
  es.addEventListener("done", () => es.close());
  es.onerror = () => {
    handlers.onConnectionError?.();
    es.close();
  };

  return () => es.close();
}
