/**
 * Single source of truth for shopper identity + consent state (CLAUDE.md
 * architecture rule 5: no persistence without explicit opt-in, no device
 * fingerprinting). `session_id` is always ephemeral (sessionStorage); `shopper_id`
 * is only ever a persistent, storage-backed id when the shopper has opted in —
 * otherwise it's just the session id, so nothing outlives the browsing session.
 */

const CONSENT_KEY = "memora_consent";
const SHOPPER_ID_KEY = "memora_shopper_id";
const SESSION_ID_KEY = "memora_session_id";

export type Consent = "persist" | "anonymous";

export function getConsent(): Consent | null {
  return sessionStorage.getItem(CONSENT_KEY) as Consent | null;
}

export function setConsent(value: Consent): void {
  sessionStorage.setItem(CONSENT_KEY, value);
}

export function isPersisting(): boolean {
  return getConsent() === "persist";
}

export function getSessionId(): string {
  let id = sessionStorage.getItem(SESSION_ID_KEY);
  if (!id) {
    id = crypto.randomUUID();
    sessionStorage.setItem(SESSION_ID_KEY, id);
  }
  return id;
}

/** Stable across visits only once the shopper has opted in; otherwise this
 * session's id, so an anonymous shopper is never trackable across sessions.
 */
export function getShopperId(): string {
  if (isPersisting()) {
    let id = localStorage.getItem(SHOPPER_ID_KEY);
    if (!id) {
      id = crypto.randomUUID();
      localStorage.setItem(SHOPPER_ID_KEY, id);
    }
    return id;
  }
  return getSessionId();
}
