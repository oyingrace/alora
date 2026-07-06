import type { MemoraConfig } from "./config";
import { deleteBelief, getAutonomyStatus, getMemory, getRecs, revokeAutonomy, sendChat } from "./api";
import { getConsent, getSessionId, getShopperId, isPersisting, setConsent } from "./identity";
import type { AuditItem, AutonomyStatus, BeliefItem } from "./api";

type Tab = "chat" | "recs" | "inspector";

const STYLE_ID = "memora-widget-styles";

function injectStyles(): void {
  if (document.getElementById(STYLE_ID)) return;
  const style = document.createElement("style");
  style.id = STYLE_ID;
  style.textContent = `
    #memora-widget-root * { box-sizing: border-box; font-family: system-ui, sans-serif; font-size: 13px; }
    #memora-widget-root [data-memora-consent-banner] {
      background: #1f2937; color: #fff; padding: 10px 12px; border-radius: 10px;
      max-width: 260px; display: flex; flex-direction: column; gap: 8px; box-shadow: 0 4px 16px rgba(0,0,0,.2);
    }
    #memora-widget-root [data-memora-consent-banner] button {
      cursor: pointer; border: none; border-radius: 6px; padding: 6px 10px; font-weight: 600;
    }
    #memora-widget-root [data-memora-consent-banner] button:first-of-type { background: #34d399; color: #052e1a; }
    #memora-widget-root [data-memora-consent-banner] button:last-of-type { background: #374151; color: #fff; }
    #memora-widget-root [data-memora-launcher] {
      width: 52px; height: 52px; border-radius: 50%; border: none; background: #1f2937; color: #fff;
      font-size: 22px; cursor: pointer; box-shadow: 0 4px 16px rgba(0,0,0,.25);
    }
    #memora-widget-root [data-memora-panel] {
      width: 320px; height: 420px; background: #fff; border-radius: 12px; box-shadow: 0 8px 30px rgba(0,0,0,.25);
      display: flex; flex-direction: column; overflow: hidden; border: 1px solid #e5e7eb;
    }
    #memora-widget-root [data-memora-tabs] { display: flex; border-bottom: 1px solid #e5e7eb; }
    #memora-widget-root [data-memora-tab] {
      flex: 1; border: none; background: none; padding: 10px 0; cursor: pointer; font-weight: 600; color: #6b7280;
    }
    #memora-widget-root [data-memora-tab][data-active="true"] { color: #111827; border-bottom: 2px solid #111827; }
    #memora-widget-root [data-memora-tab-content] { flex: 1; overflow-y: auto; padding: 10px; }
    #memora-widget-root [data-memora-chat-messages] { display: flex; flex-direction: column; gap: 6px; }
    #memora-widget-root [data-memora-msg] { padding: 6px 10px; border-radius: 10px; max-width: 85%; }
    #memora-widget-root [data-memora-msg][data-role="user"] { align-self: flex-end; background: #111827; color: #fff; }
    #memora-widget-root [data-memora-msg][data-role="assistant"] { align-self: flex-start; background: #f3f4f6; }
    #memora-widget-root [data-memora-chat-input-row] {
      display: flex; gap: 6px; padding: 8px; border-top: 1px solid #e5e7eb;
    }
    #memora-widget-root [data-memora-chat-input] { flex: 1; border: 1px solid #d1d5db; border-radius: 6px; padding: 6px 8px; }
    #memora-widget-root [data-memora-chat-send] {
      border: none; background: #111827; color: #fff; border-radius: 6px; padding: 6px 12px; cursor: pointer;
    }
    #memora-widget-root [data-memora-rec-card], #memora-widget-root [data-memora-belief-card] {
      border: 1px solid #e5e7eb; border-radius: 8px; padding: 8px; margin-bottom: 8px;
    }
    #memora-widget-root [data-memora-belief-meta] { color: #6b7280; font-size: 11px; margin-top: 2px; }
    #memora-widget-root [data-memora-belief-delete] {
      border: none; background: #fee2e2; color: #991b1b; border-radius: 6px; padding: 4px 8px;
      cursor: pointer; margin-top: 6px; font-size: 12px;
    }
    #memora-widget-root [data-memora-audit-row] { color: #6b7280; font-size: 11px; padding: 4px 0; border-top: 1px dashed #e5e7eb; }
    #memora-widget-root [data-memora-empty] { color: #9ca3af; padding: 12px 0; text-align: center; }
    #memora-widget-root [data-memora-refresh] {
      border: 1px solid #d1d5db; background: #fff; border-radius: 6px; padding: 4px 10px; cursor: pointer;
      margin-bottom: 8px; font-size: 12px;
    }
    #memora-widget-root [data-memora-autonomy] {
      background: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 8px; padding: 8px; margin-bottom: 10px;
      font-size: 12px; color: #14532d;
    }
    #memora-widget-root [data-memora-autonomy-revoke] {
      border: none; background: #fff; color: #b91c1c; border: 1px solid #fecaca; border-radius: 6px;
      padding: 3px 8px; cursor: pointer; margin-top: 6px; font-size: 11px;
    }
  `;
  document.head.appendChild(style);
}

/**
 * Mounts the floating widget: consent banner first, then a launcher button that
 * opens a panel with chat / recs / Memory Inspector tabs. Persistence never
 * happens before explicit opt-in (CLAUDE.md architecture rule 5) — declining
 * still gets a working chat, just backed by the ephemeral session store instead
 * of Postgres (see apps/api/app/services/session_store.py).
 */
export function mountWidget(config: MemoraConfig): void {
  injectStyles();

  const root = document.createElement("div");
  root.id = "memora-widget-root";
  root.style.position = "fixed";
  root.style.bottom = "16px";
  root.style.right = "16px";
  root.style.zIndex = "2147483647";
  document.body.appendChild(root);

  let panelOpen = false;
  let activeTab: Tab = "chat";
  const chatHistory: { role: "user" | "assistant"; content: string }[] = [];

  function render(): void {
    root.replaceChildren();
    if (!getConsent()) {
      root.appendChild(buildConsentBanner());
      return;
    }
    if (!panelOpen) {
      root.appendChild(buildLauncherButton());
      return;
    }
    root.appendChild(buildPanel());
  }

  function buildConsentBanner(): HTMLElement {
    const banner = document.createElement("div");
    banner.setAttribute("data-memora-consent-banner", "");

    const label = document.createElement("div");
    label.textContent = "Want me to remember you?";
    banner.appendChild(label);

    const persistBtn = document.createElement("button");
    persistBtn.textContent = "Remember me";
    persistBtn.onclick = () => {
      setConsent("persist");
      render();
    };

    const anonBtn = document.createElement("button");
    anonBtn.textContent = "Stay anonymous this session";
    anonBtn.onclick = () => {
      setConsent("anonymous");
      render();
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
      panelOpen = true;
      render();
    };
    return button;
  }

  function buildPanel(): HTMLElement {
    const panel = document.createElement("div");
    panel.setAttribute("data-memora-panel", "");

    const tabs = document.createElement("div");
    tabs.setAttribute("data-memora-tabs", "");
    const content = document.createElement("div");
    content.setAttribute("data-memora-tab-content", "");

    const tabDefs: { key: Tab; label: string }[] = [
      { key: "chat", label: "Chat" },
      { key: "recs", label: "For you" },
      { key: "inspector", label: "Memory" },
    ];

    for (const { key, label } of tabDefs) {
      const tabBtn = document.createElement("button");
      tabBtn.setAttribute("data-memora-tab", "");
      tabBtn.dataset.active = String(activeTab === key);
      tabBtn.textContent = label;
      tabBtn.onclick = () => {
        activeTab = key;
        render();
      };
      tabs.appendChild(tabBtn);
    }

    panel.append(tabs, content);
    renderTabContent(content);
    return panel;
  }

  function renderTabContent(content: HTMLElement): void {
    content.replaceChildren(loadingNode());
    if (activeTab === "chat") {
      renderChatTab(content);
    } else if (activeTab === "recs") {
      renderRecsTab(content);
    } else {
      renderInspectorTab(content);
    }
  }

  function loadingNode(): HTMLElement {
    const el = document.createElement("div");
    el.setAttribute("data-memora-empty", "");
    el.textContent = "Loading…";
    return el;
  }

  function renderChatTab(content: HTMLElement): void {
    const wrapper = document.createElement("div");
    wrapper.style.display = "flex";
    wrapper.style.flexDirection = "column";
    wrapper.style.height = "100%";

    const messages = document.createElement("div");
    messages.setAttribute("data-memora-chat-messages", "");
    messages.style.flex = "1";
    messages.style.overflowY = "auto";

    const renderMessages = () => {
      messages.replaceChildren();
      if (chatHistory.length === 0) {
        const empty = document.createElement("div");
        empty.setAttribute("data-memora-empty", "");
        empty.textContent = "Ask me anything about products, or what I remember about you.";
        messages.appendChild(empty);
        return;
      }
      for (const msg of chatHistory) {
        const bubble = document.createElement("div");
        bubble.setAttribute("data-memora-msg", "");
        bubble.dataset.role = msg.role;
        bubble.textContent = msg.content;
        messages.appendChild(bubble);
      }
      messages.scrollTop = messages.scrollHeight;
    };
    renderMessages();

    const inputRow = document.createElement("div");
    inputRow.setAttribute("data-memora-chat-input-row", "");
    const input = document.createElement("input");
    input.setAttribute("data-memora-chat-input", "");
    input.placeholder = "Message…";
    const sendBtn = document.createElement("button");
    sendBtn.setAttribute("data-memora-chat-send", "");
    sendBtn.textContent = "Send";

    const send = async () => {
      const text = input.value.trim();
      if (!text) return;
      input.value = "";
      chatHistory.push({ role: "user", content: text });
      renderMessages();

      try {
        const result = await sendChat(
          config,
          getShopperId(),
          getSessionId(),
          text,
          isPersisting()
        );
        chatHistory.push({ role: "assistant", content: result.reply });
      } catch {
        chatHistory.push({
          role: "assistant",
          content: "Sorry, I couldn't reach the assistant just now.",
        });
      }
      renderMessages();
    };

    sendBtn.onclick = () => void send();
    input.onkeydown = (e) => {
      if (e.key === "Enter") void send();
    };

    inputRow.append(input, sendBtn);
    wrapper.append(messages, inputRow);
    content.replaceChildren(wrapper);
  }

  function renderRecsTab(content: HTMLElement): void {
    const refresh = document.createElement("button");
    refresh.setAttribute("data-memora-refresh", "");
    refresh.textContent = "Refresh";

    const list = document.createElement("div");

    const load = async () => {
      list.replaceChildren(loadingNode());
      try {
        const result = await getRecs(config, getShopperId());
        list.replaceChildren();
        if (result.recommendations.length === 0) {
          const empty = document.createElement("div");
          empty.setAttribute("data-memora-empty", "");
          empty.textContent = "Nothing to recommend yet — browse a bit first.";
          list.appendChild(empty);
          return;
        }
        for (const rec of result.recommendations) {
          const card = document.createElement("div");
          card.setAttribute("data-memora-rec-card", "");
          const name = document.createElement("div");
          name.textContent = rec.name;
          name.style.fontWeight = "600";
          const price = document.createElement("div");
          price.textContent = `${rec.currency} ${rec.price.toFixed(2)} · ${rec.category}`;
          price.style.color = "#6b7280";
          card.append(name, price);
          list.appendChild(card);
        }
      } catch {
        list.replaceChildren();
        const err = document.createElement("div");
        err.setAttribute("data-memora-empty", "");
        err.textContent = "Couldn't load recommendations right now.";
        list.appendChild(err);
      }
    };

    refresh.onclick = () => void load();
    content.replaceChildren(refresh, list);
    void load();
  }

  function renderInspectorTab(content: HTMLElement): void {
    const autonomySection = document.createElement("div");
    const list = document.createElement("div");

    const loadAutonomy = async () => {
      try {
        const status = await getAutonomyStatus(config, getShopperId());
        renderAutonomyStatus(autonomySection, status, loadAutonomy);
      } catch {
        autonomySection.replaceChildren();
      }
    };

    const load = async () => {
      list.replaceChildren(loadingNode());
      try {
        const result = await getMemory(config, getShopperId());
        renderBeliefs(list, result.beliefs, result.audit, load);
      } catch {
        list.replaceChildren();
        const err = document.createElement("div");
        err.setAttribute("data-memora-empty", "");
        err.textContent = "Couldn't load your memory right now.";
        list.appendChild(err);
      }
    };

    content.replaceChildren(autonomySection, list);
    void loadAutonomy();
    void load();
  }

  function renderAutonomyStatus(
    container: HTMLElement,
    status: AutonomyStatus,
    reload: () => void
  ): void {
    container.replaceChildren();
    // Nothing to show until there's at least one reorder decision on record.
    if (status.approvals === 0 && status.rejections === 0) return;

    const box = document.createElement("div");
    box.setAttribute("data-memora-autonomy", "");

    const label = document.createElement("div");
    const levelLabel =
      status.level >= 2
        ? "Auto-reorder is on — I'll reorder and notify you"
        : status.level === 1
          ? "I'll ask before reordering"
          : "Reorder autonomy is off";
    label.textContent = `${levelLabel} · ${status.approvals} approved, ${status.rejections} declined`;
    box.appendChild(label);

    if (status.level > 0) {
      const revokeBtn = document.createElement("button");
      revokeBtn.setAttribute("data-memora-autonomy-revoke", "");
      revokeBtn.textContent = "Turn off";
      revokeBtn.onclick = async () => {
        revokeBtn.disabled = true;
        try {
          await revokeAutonomy(config, getShopperId());
          reload();
        } catch {
          revokeBtn.disabled = false;
        }
      };
      box.appendChild(revokeBtn);
    }

    container.appendChild(box);
  }

  function renderBeliefs(
    list: HTMLElement,
    beliefs: BeliefItem[],
    audit: AuditItem[],
    reload: () => void
  ): void {
    list.replaceChildren();
    if (beliefs.length === 0) {
      const empty = document.createElement("div");
      empty.setAttribute("data-memora-empty", "");
      empty.textContent = "Nothing remembered yet.";
      list.appendChild(empty);
      return;
    }

    for (const belief of beliefs) {
      const card = document.createElement("div");
      card.setAttribute("data-memora-belief-card", "");
      if (belief.status !== "active") {
        card.style.opacity = "0.55";
      }

      const statement = document.createElement("div");
      statement.textContent = belief.statement;

      const meta = document.createElement("div");
      meta.setAttribute("data-memora-belief-meta", "");
      meta.textContent = `${belief.category} · ${Math.round(belief.confidence * 100)}% confident · ${belief.status}`;

      card.append(statement, meta);

      // Deprecated beliefs are already forgotten — nothing left to delete.
      if (belief.status !== "deprecated") {
        const deleteBtn = document.createElement("button");
        deleteBtn.setAttribute("data-memora-belief-delete", "");
        deleteBtn.textContent = "Forget this";
        deleteBtn.onclick = async () => {
          deleteBtn.disabled = true;
          deleteBtn.textContent = "Forgetting…";
          try {
            await deleteBelief(config, belief.id, "shopper deleted it in the Inspector");
            reload();
          } catch {
            deleteBtn.disabled = false;
            deleteBtn.textContent = "Forget this";
          }
        };
        card.appendChild(deleteBtn);
      }

      list.appendChild(card);
    }

    if (audit.length > 0) {
      const auditHeader = document.createElement("div");
      auditHeader.style.marginTop = "10px";
      auditHeader.style.fontWeight = "600";
      auditHeader.textContent = "Audit log";
      list.appendChild(auditHeader);

      for (const entry of audit.slice(0, 10)) {
        const row = document.createElement("div");
        row.setAttribute("data-memora-audit-row", "");
        row.textContent = `${entry.action}: ${entry.reason}`;
        list.appendChild(row);
      }
    }
  }

  render();
}
