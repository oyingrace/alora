import type { MemoraConfig } from "./config";

export type EventKind =
  | "search"
  | "view"
  | "dwell"
  | "add_to_cart"
  | "purchase"
  | "chat"
  | "correction";

export interface MemoraEvent {
  kind: EventKind;
  payload: Record<string, unknown>;
}

const SESSION_STORAGE_KEY = "memora_session_id";

function getSessionId(): string {
  let id = sessionStorage.getItem(SESSION_STORAGE_KEY);
  if (!id) {
    id = crypto.randomUUID();
    sessionStorage.setItem(SESSION_STORAGE_KEY, id);
  }
  return id;
}

/** Posts a single event to the first-party /events ingest endpoint. Fire-and-forget. */
export function sendEvent(config: MemoraConfig, event: MemoraEvent): void {
  const body = JSON.stringify({
    store_id: config.storeId,
    session_id: getSessionId(),
    kind: event.kind,
    payload: event.payload,
  });

  const url = `${config.apiBaseUrl}/events`;
  if (navigator.sendBeacon) {
    navigator.sendBeacon(url, new Blob([body], { type: "application/json" }));
    return;
  }
  fetch(url, { method: "POST", body, headers: { "Content-Type": "application/json" }, keepalive: true }).catch(
    () => {
      // Best-effort telemetry: swallow network errors, never block the shopper.
    }
  );
}

/** Wires up capture for view (immediate) and add-to-cart (delegated click) events. */
export function attachEventCapture(config: MemoraConfig): void {
  sendEvent(config, { kind: "view", payload: { path: location.pathname } });

  document.addEventListener("click", (evt) => {
    const target = (evt.target as HTMLElement)?.closest<HTMLElement>("[data-memora-add-to-cart]");
    if (!target) return;
    sendEvent(config, {
      kind: "add_to_cart",
      payload: { product_id: target.dataset.memoraAddToCart },
    });
  });
}
