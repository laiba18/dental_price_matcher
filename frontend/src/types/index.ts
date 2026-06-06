export interface PipelineResult {
  order_id: number;
  order_ref?: string;
  order_date?: string;
  patient_name?: string;
  line_items: number;
  high_conf_parses: number;
  exact_matches: number;
  equiv_recommendations: number;
  total_potential_savings: number;
  output_price_match: string;
  output_alternate: string;
  output_evidence: string;
}

export interface ProgressEvent {
  step: number;
  pct: number;
  label: string;
  item_index?: number;
  item_total?: number;
  substep?: string;
  detail?: string;
  item_description?: string;
  prices_found?: number;
  filename?: string;
  order_ref?: string | null;
  order_id?: number;
  order_date?: string | null;
}

export interface OrderMeta {
  filename?: string;
  order_ref?: string | null;
  order_id?: number;
  order_date?: string | null;
}

export type ItemSubstep =
  | "pending"
  | "parse"
  | "parsed"
  | "search"
  | "scrape"
  | "price_found"
  | "done"
  | "no_results"
  | "starting";

export interface ItemProcessingState {
  index: number;
  description: string;
  substep: ItemSubstep;
  substepLabel: string;
  detail: string;
  pricesFound?: number;
}

export interface PipelineStep {
  id: number;
  name: string;
  description: string;
  pctStart: number;
  pctEnd: number;
}

export type LogLevel = "info" | "warn" | "error" | "progress" | "warning";

export interface PipelineLogEntry {
  id: string;
  ts: number;
  level: LogLevel;
  message: string;
  pct?: number;
}

export interface PipelineProgressState {
  progress: number;
  currentStep: number;
  statusLabel: string;
  warnings: string[];
  logs: PipelineLogEntry[];
  itemIndex?: number;
  itemTotal?: number;
  substep?: string;
  detail?: string;
  items: ItemProcessingState[];
  orderMeta?: OrderMeta;
}

export interface OutputFile {
  id: string;
  filename: string;
  label: string;
  description: string;
  variant: "primary" | "secondary" | "neutral";
}

export type PipelinePhase = "idle" | "uploading" | "processing" | "complete" | "error";

export type OrderStatus = "pending" | "processing" | "complete" | "failed";

export interface AuthUser {
  email: string;
  name: string;
}

export interface OrderRecord {
  id: number;
  filename: string;
  order_ref?: string | null;
  order_date?: string | null;
  patient_name?: string | null;
  total_price?: number | null;
  item_count?: number | null;
  status: OrderStatus | string;
  error_message?: string | null;
  output_price_match?: string | null;
  output_alternate?: string | null;
  output_evidence?: string | null;
  created_at: string;
}
