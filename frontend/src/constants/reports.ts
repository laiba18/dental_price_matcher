import type { OutputFile, PipelineResult } from "../types";

export const REPORT_DEFINITIONS: Omit<OutputFile, "filename">[] = [
  {
    id: "price_match",
    label: "Price Match Report",
    description: "Exact matches sorted by savings — hand to your rep",
    variant: "primary",
  },
  {
    id: "alternate",
    label: "Alternate Purchase List",
    description: "Equivalency-driven items to buy direct",
    variant: "secondary",
  },
  {
    id: "evidence",
    label: "Background Evidence",
    description: "All prices, URLs, and match confidence data",
    variant: "neutral",
  },
];

export function getReportFilename(
  source: Pick<
    PipelineResult,
    "output_price_match" | "output_alternate" | "output_evidence"
  >,
  id: string,
): string {
  switch (id) {
    case "price_match":
      return source.output_price_match;
    case "alternate":
      return source.output_alternate;
    case "evidence":
      return source.output_evidence;
    default:
      return "";
  }
}

export function getOrderReportFilename(
  order: {
    output_price_match?: string | null;
    output_alternate?: string | null;
    output_evidence?: string | null;
  },
  id: string,
): string {
  switch (id) {
    case "price_match":
      return order.output_price_match ?? "";
    case "alternate":
      return order.output_alternate ?? "";
    case "evidence":
      return order.output_evidence ?? "";
    default:
      return "";
  }
}
