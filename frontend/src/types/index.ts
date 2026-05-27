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
}

export interface PipelineStep {
  id: number;
  name: string;
  description: string;
}

export interface OutputFile {
  id: string;
  filename: string;
  label: string;
  description: string;
  variant: "primary" | "secondary" | "neutral";
}

export type PipelinePhase = "idle" | "uploading" | "processing" | "complete" | "error";

export interface AuthUser {
  email: string;
  name: string;
}
