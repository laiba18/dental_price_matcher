import type { ItemProcessingState, ItemSubstep, ProgressEvent } from "../types";

export const SUBSTEP_EXPLANATIONS: Record<string, string> = {
  starting:
    "The system is preparing to process each line item from your PDF one by one.",
  parse:
    "Groq AI reads the raw product description and extracts brand, product name, and pack size.",
  parsed:
    "Description understood. Next, the system builds search queries to find this product online.",
  search:
    "Firecrawl searches Google for supplier pages that sell this exact (or similar) product.",
  scrape:
    "The system opens a supplier product page and reads the page content to extract the price.",
  price_found:
    "A price was found on a supplier website and is being verified against your order item.",
  done: "This item is finished. The system moves on to the next line item.",
  no_results:
    "No public prices were found for this item. It will still appear in your reports.",
  pending: "This item has not been processed yet.",
};

export function mapSubstep(raw?: string): ItemSubstep {
  const allowed: ItemSubstep[] = [
    "parse", "parsed", "search", "scrape", "price_found",
    "done", "no_results", "starting", "pending",
  ];
  if (raw && allowed.includes(raw as ItemSubstep)) return raw as ItemSubstep;
  return "search";
}

export function updateItemStates(
  prev: ItemProcessingState[],
  data: ProgressEvent,
): ItemProcessingState[] {
  if (!data.item_total) return prev;

  let items =
    prev.length === data.item_total
      ? [...prev]
      : Array.from({ length: data.item_total }, (_, i) => ({
          index: i + 1,
          description: "",
          substep: "pending" as ItemSubstep,
          substepLabel: "Waiting…",
          detail: "Queued for processing",
          pricesFound: undefined as number | undefined,
        }));

  if (data.item_index != null && data.item_index > 0) {
    items = items.map((it) => {
      if (it.index < data.item_index!) {
        const prevItem = prev.find((p) => p.index === it.index) ?? it;
        const wasNoResults = prevItem.substep === "no_results";
        return {
          ...prevItem,
          substep: wasNoResults ? "no_results" : "done",
          substepLabel: wasNoResults
            ? "No prices found"
            : prevItem.pricesFound
              ? `${prevItem.pricesFound} price(s) found`
              : "Complete",
        };
      }
      if (it.index === data.item_index) {
        const substep = mapSubstep(data.substep);
        return {
          ...it,
          description: data.item_description || it.description,
          substep,
          substepLabel: data.label.replace(/^Item \d+\/\d+:\s*/, ""),
          detail: data.detail || data.label,
          pricesFound: data.prices_found ?? it.pricesFound,
        };
      }
      return it;
    });
  } else if (data.item_total && data.substep === "starting") {
    // At 20% — show all items queued before first item starts
    items = items.map((it) => ({
      ...it,
      substepLabel: it.index === 1 ? "Starting soon…" : "Queued…",
    }));
  }

  return items;
}

export function getSubstepExplanation(substep?: string): string {
  if (!substep) return SUBSTEP_EXPLANATIONS.search;
  return SUBSTEP_EXPLANATIONS[substep] ?? SUBSTEP_EXPLANATIONS.search;
}
