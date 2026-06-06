import type { PipelineStep } from "../types";

export const PIPELINE_STEPS: PipelineStep[] = [
  {
    id: 1,
    name: "PDF Extraction",
    description: "Reading line items from order PDF",
    pctStart: 0,
    pctEnd: 15,
  },
  {
    id: 2,
    name: "Price Intelligence",
    description: "Parsing descriptions & searching supplier prices",
    pctStart: 15,
    pctEnd: 72,
  },
  {
    id: 3,
    name: "Matching",
    description: "Scoring matches & evaluating equivalencies",
    pctStart: 72,
    pctEnd: 86,
  },
  {
    id: 4,
    name: "Reports",
    description: "Generating Excel output files",
    pctStart: 86,
    pctEnd: 100,
  },
];

export const PIPELINE_MILESTONES = [
  { pct: 5, label: "Reading PDF" },
  { pct: 15, label: "Line items extracted" },
  { pct: 20, label: "Price search started" },
  { pct: 72, label: "All items searched" },
  { pct: 86, label: "Matches scored" },
  { pct: 90, label: "Reports generating" },
  { pct: 100, label: "Complete" },
];

export function getStepProgress(step: PipelineStep, overallPct: number): number {
  if (overallPct <= step.pctStart) return 0;
  if (overallPct >= step.pctEnd) return 100;
  const range = step.pctEnd - step.pctStart;
  return Math.round(((overallPct - step.pctStart) / range) * 100);
}
