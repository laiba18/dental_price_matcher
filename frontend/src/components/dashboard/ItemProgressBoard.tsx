import { getSubstepExplanation } from "../../utils/itemProgress";
import type { ItemProcessingState } from "../../types";
import "./ItemProgressBoard.css";

interface ItemProgressBoardProps {
  items: ItemProcessingState[];
  currentIndex?: number;
}

function statusIcon(substep: ItemProcessingState["substep"]) {
  switch (substep) {
    case "done":
      return "✓";
    case "no_results":
      return "—";
    case "pending":
      return "○";
    default:
      return "◉";
  }
}

export function ItemProgressBoard({ items, currentIndex }: ItemProgressBoardProps) {
  if (items.length === 0) return null;

  const done = items.filter((i) => i.substep === "done" || i.substep === "no_results").length;

  return (
    <div className="item-board">
      <div className="item-board__header">
        <span className="item-board__title">Line items ({done}/{items.length} processed)</span>
        <span className="item-board__hint">Each item: parse → search web → scrape pages → extract price</span>
      </div>

      <div className="item-board__list">
        {items.map((item) => {
          const isActive = item.index === currentIndex;
          const isDone = item.substep === "done" || item.substep === "no_results";

          return (
            <div
              key={item.index}
              className={`item-board__row item-board__row--${item.substep} ${
                isActive ? "item-board__row--active" : ""
              } ${isDone ? "item-board__row--finished" : ""}`}
            >
              <span className="item-board__num">{statusIcon(item.substep)}</span>
              <div className="item-board__body">
                <div className="item-board__top">
                  <span className="item-board__index">#{item.index}</span>
                  <span className="item-board__status">{item.substepLabel}</span>
                </div>
                {item.description && (
                  <p className="item-board__desc">{item.description}</p>
                )}
                {isActive && item.detail && (
                  <p className="item-board__detail">{item.detail}</p>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

interface CurrentActionPanelProps {
  substep?: string;
  detail?: string;
  label: string;
  itemIndex?: number;
  itemTotal?: number;
}

export function CurrentActionPanel({
  substep,
  detail,
  label,
  itemIndex,
  itemTotal,
}: CurrentActionPanelProps) {
  const explanation = getSubstepExplanation(substep);

  return (
    <div className="current-action">
      <span className="current-action__badge">
        {itemIndex && itemTotal ? `Item ${itemIndex} of ${itemTotal}` : "Processing"}
      </span>
      <h4 className="current-action__title">{label}</h4>
      <p className="current-action__explain">{explanation}</p>
      {detail && detail !== label && (
        <p className="current-action__detail">{detail}</p>
      )}

      <div className="current-action__flow">
        <FlowStep done={isPast(substep, "parse")} active={substep === "parse"} label="1. Parse description" />
        <FlowStep done={isPast(substep, "parsed")} active={substep === "parsed"} label="2. Build queries" />
        <FlowStep done={isPast(substep, "search")} active={substep === "search"} label="3. Web search" />
        <FlowStep done={isPast(substep, "scrape")} active={substep === "scrape"} label="4. Scrape page" />
        <FlowStep done={isPast(substep, "price_found")} active={substep === "price_found"} label="5. Extract price" />
        <FlowStep done={substep === "done" || substep === "no_results"} active={false} label="6. Done" />
      </div>
    </div>
  );
}

function isPast(current: string | undefined, target: string): boolean {
  const order = ["parse", "parsed", "search", "scrape", "price_found", "done", "no_results"];
  const ci = order.indexOf(current ?? "");
  const ti = order.indexOf(target);
  if (ci < 0 || ti < 0) return false;
  return ci > ti || current === "done" || current === "no_results";
}

function FlowStep({
  done,
  active,
  label,
}: {
  done: boolean;
  active: boolean;
  label: string;
}) {
  return (
    <div
      className={`flow-step ${done ? "flow-step--done" : ""} ${active ? "flow-step--active" : ""}`}
    >
      <span className="flow-step__dot" />
      <span className="flow-step__label">{label}</span>
    </div>
  );
}
