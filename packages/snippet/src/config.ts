export interface MemoraConfig {
  storeId: string;
  apiBaseUrl: string;
}

const DEFAULT_API_BASE_URL = "https://api.memora.example";

/** Reads config off the currently-executing <script> tag's data-* attributes. */
export function readConfig(currentScript: HTMLOrSVGScriptElement | null): MemoraConfig {
  const el = currentScript as HTMLScriptElement | null;
  const storeId = el?.dataset.storeId;
  if (!storeId) {
    throw new Error("Memora snippet: missing required data-store-id attribute");
  }
  return {
    storeId,
    apiBaseUrl: el?.dataset.apiBase ?? DEFAULT_API_BASE_URL,
  };
}
