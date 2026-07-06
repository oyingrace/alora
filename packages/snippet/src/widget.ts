import type { MemoraConfig } from "./config";

const CONSENT_STORAGE_KEY = "memora_consent";

type Consent = "persist" | "anonymous";

function getConsent(): Consent | null {
  return sessionStorage.getItem(CONSENT_STORAGE_KEY) as Consent | null;
}

function setConsent(value: Consent): void {
  sessionStorage.setItem(CONSENT_STORAGE_KEY, value);
}

/**
 * Mounts the floating widget shell (launcher button + consent banner).
 * Chat, recs rail, and Memory Inspector tabs are filled in during Phase 3 —
 * this scaffold only owns mount points and the consent gate, since persistence
 * must never happen before explicit opt-in (see CLAUDE.md architecture rule 5).
 */
export function mountWidget(config: MemoraConfig): void {
  const root = document.createElement("div");
  root.id = "memora-widget-root";
  root.style.position = "fixed";
  root.style.bottom = "16px";
  root.style.right = "16px";
  root.style.zIndex = "2147483647";
  document.body.appendChild(root);

  if (!getConsent()) {
    root.appendChild(buildConsentBanner());
  } else {
    root.appendChild(buildLauncherButton());
  }

  function buildConsentBanner(): HTMLElement {
    const banner = document.createElement("div");
    banner.setAttribute("data-memora-consent-banner", "");
    banner.textContent = "Want me to remember you? ";

    const persistBtn = document.createElement("button");
    persistBtn.textContent = "Remember me";
    persistBtn.onclick = () => {
      setConsent("persist");
      root.replaceChildren(buildLauncherButton());
    };

    const anonBtn = document.createElement("button");
    anonBtn.textContent = "Stay anonymous this session";
    anonBtn.onclick = () => {
      setConsent("anonymous");
      root.replaceChildren(buildLauncherButton());
    };

    banner.append(persistBtn, anonBtn);
    return banner;
  }

  function buildLauncherButton(): HTMLElement {
    const button = document.createElement("button");
    button.setAttribute("data-memora-launcher", "");
    button.setAttribute("aria-label", "Open Memora shopping assistant");
    button.textContent = "💬";
    button.onclick = () => {
      // Chat panel / recs rail / Inspector tabs mount here in Phase 3.
      console.info(`[memora] launcher clicked for store ${config.storeId}`);
    };
    return button;
  }
}
