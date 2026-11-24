"use strict";
// Staff knowledge editor uses local SQLite only. All guest/staff text uses textContent.
const get = (id) => document.getElementById(id);
const make = (tag, value, cls) => {
  const node = document.createElement(tag);
  if (value !== undefined) node.textContent = value;
  if (cls) node.className = cls;
  return node;
};
let contextRevision = 0;
let pendingDraft = null;
let creating = false;

function resetKnowledge(message) {
  contextRevision++;
  pendingDraft = null;
  get("knowledge-data").hidden = true;
  get("knowledge-empty").hidden = false;
  for (const id of ["facts", "drafts", "revisions"]) get(id).replaceChildren();
  get("loaded-property").textContent = "—";
  get("draft-form").reset();
  get("review-reason").value = "";
  get("preview-question").value = "";
  get("preview-result").textContent = "No public question checked.";
  get("draft-message").textContent = "";
  get("message").textContent = message;
  get("load-knowledge").disabled = false;
}

function endpoint() {
  return "/api/properties/" + encodeURIComponent(get("property").value);
}

async function request(path, method = "GET", data, key = get("staff-key").value) {
  if (!key.trim()) throw Error("Enter a development staff key.");
  const headers = {"X-Staff-Key": key};
  if (data !== undefined) headers["Content-Type"] = "application/json";
  const response = await fetch(path, {
    method, headers, cache: "no-store",
    body: data === undefined ? undefined : JSON.stringify(data)
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw Error(typeof body.detail === "string" ? body.detail : "Request failed.");
  }
  return body;
}

function empty(parent, text) {
  parent.append(make("p", text, "workspace-subtitle"));
}

function actionButton(text, handler) {
  const button = make("button", text, "button secondary compact");
  button.type = "button";
  button.addEventListener("click", () => handler(button));
  return button;
}

function renderFacts(facts) {
  const root = get("facts");
  root.replaceChildren();
  if (!facts.length) return empty(root, "No approved knowledge in this demo hotel.");
  for (const fact of facts) {
    const card = make("article", undefined, "knowledge-card");
    const title = make("div", undefined, "case-card-head");
    title.append(
      make("strong", fact.question_key.replaceAll("_", " ")),
      make("span", fact.approved ? "Published in local FAQ" : "Withdrawn", "status-pill " + (fact.approved ? "claimed" : "queued"))
    );
    card.append(title, make("p", fact.answer, "case-detail"));
    card.append(make("p", "Version " + fact.version + " · Source: " + fact.source, "workspace-tip"));
    if (fact.approved) card.append(actionButton("Withdraw from guest FAQ", button => {
      const reason = get("review-reason").value.trim();
      if (reason.length < 8) {
        get("message").textContent = "Enter a withdrawal explanation of at least 8 characters.";
        get("review-reason").focus();
        return;
      }
      return runAction(
        button, endpoint() + "/staff/knowledge/" + encodeURIComponent(fact.question_key) + "/withdraw",
        {reason}, "Knowledge withdrawn locally."
      );
    }));
    root.append(card);
  }
}

function renderDrafts(drafts) {
  const root = get("drafts");
  root.replaceChildren();
  const pending = drafts.filter(d => d.status === "draft");
  if (!pending.length) return empty(root, "No drafts awaiting review.");
  for (const draft of pending) {
    const card = make("article", undefined, "knowledge-card");
    const header = make("div", undefined, "case-card-head");
    header.append(make("strong", draft.question_key.replaceAll("_", " ")),
      make("span", "Unpublished draft", "status-pill queued"));
    card.append(header,
      make("p", draft.answer, "case-detail"),
      make("p", "Based on version " + draft.base_version + " · Source reference: " + draft.source_reference, "workspace-tip"));
    const actions = make("div", undefined, "case-actions");
    actions.append(actionButton("Approve local version", button =>
      runAction(
        button, endpoint() + "/staff/knowledge/drafts/" + encodeURIComponent(draft.id) + "/approve",
        undefined, "Local knowledge version approved."
      )
    ));
    actions.append(actionButton("Reject draft", button => {
      const reason = get("review-reason").value.trim();
      if (reason.length < 8) {
        get("message").textContent = "Enter a rejection explanation of at least 8 characters.";
        get("review-reason").focus();
        return;
      }
      return runAction(
        button, endpoint() + "/staff/knowledge/drafts/" + encodeURIComponent(draft.id) + "/reject",
        {reason}, "Draft rejected; public knowledge unchanged."
      );
    }));
    card.append(actions);
    root.append(card);
  }
}

function renderRevisions(history) {
  const root = get("revisions");
  root.replaceChildren();
  if (!history.length) return empty(root, "No managed revisions recorded yet.");
  for (const entry of history) {
    const item = make("article", undefined, "knowledge-revision");
    item.append(
      make("strong", entry.question_key + " · v" + entry.version + (entry.approved ? " · approved" : " · withdrawn")),
      make("p", entry.answer, "workspace-subtitle"),
      make("span", "Development actor: " + entry.actor, "workspace-tip")
    );
    root.append(item);
  }
}

async function loadKnowledge() {
  const property = get("property").value;
  const key = get("staff-key").value;
  if (!key.trim()) return resetKnowledge("Enter a development key for this hotel first.");
  const revision = ++contextRevision;
  get("knowledge-data").hidden = true;
  get("knowledge-empty").hidden = false;
  get("load-knowledge").disabled = true;
  get("message").textContent = "Loading approved facts and unpublished drafts from local SQLite...";
  try {
    const root = endpoint() + "/staff/knowledge";
    const [list, history] = await Promise.all([
      request(root, "GET", undefined, key),
      request(root + "/history", "GET", undefined, key)
    ]);
    if (revision !== contextRevision) return;
    if (list.property !== property || history.property !== property ||
        list.source !== "local_sqlite_development" ||
        list.production_approval !== false || history.production_approval !== false ||
        !Array.isArray(list.facts) || !Array.isArray(list.drafts) || !Array.isArray(history.history)) {
      throw Error("Unverified property or knowledge response.");
    }
    renderFacts(list.facts);
    renderDrafts(list.drafts);
    renderRevisions(history.history);
    get("loaded-property").textContent = property;
    get("knowledge-empty").hidden = true;
    get("knowledge-data").hidden = false;
    get("message").textContent = "Local knowledge loaded for " + property + ". Only approved versions are visible to guests.";
  } catch (error) {
    if (revision !== contextRevision) return;
    get("knowledge-data").hidden = true;
    get("knowledge-empty").hidden = false;
    for (const id of ["facts", "drafts", "revisions"]) get(id).replaceChildren();
    get("message").textContent = "Unable to load knowledge: " + error.message;
  } finally {
    if (revision === contextRevision) get("load-knowledge").disabled = false;
  }
}

async function runAction(button, url, body, success) {
  const revision = contextRevision;
  const key = get("staff-key").value;
  button.disabled = true;
  get("message").textContent = "Recording reviewed knowledge change...";
  try {
    await request(url, "POST", body, key);
    if (revision !== contextRevision) return;
    get("review-reason").value = "";
    await loadKnowledge();
    if (revision + 1 === contextRevision) get("message").textContent = success;
  } catch (error) {
    if (revision === contextRevision) {
      get("message").textContent = "Knowledge change not confirmed: " + error.message + ". Refresh before retrying.";
    }
  } finally {
    button.disabled = false;
  }
}

function newDraftKey(draft) {
  const snapshot = JSON.stringify({property: get("property").value, ...draft});
  if (!pendingDraft || pendingDraft.snapshot !== snapshot) {
    if (!globalThis.crypto?.randomUUID) throw Error("Secure random UUID unavailable; use localhost or HTTPS.");
    pendingDraft = {snapshot, key: crypto.randomUUID().replaceAll("-", "")};
  }
  return {...draft, request_key: pendingDraft.key};
}

get("draft-form").addEventListener("submit", async event => {
  event.preventDefault();
  if (creating || !event.currentTarget.reportValidity()) return;
  const revision = contextRevision;
  const key = get("staff-key").value;
  const button = get("draft-submit");
  creating = true;
  button.disabled = true;
  try {
    const payload = newDraftKey({
      question_key: get("question-key").value,
      answer: get("draft-answer").value.trim(),
      source_reference: get("source-reference").value.trim(),
    });
    const result = await request(endpoint() + "/staff/knowledge/drafts", "POST", payload, key);
    if (revision !== contextRevision) return;
    pendingDraft = null;
    get("draft-form").reset();
    await loadKnowledge();
    get("draft-message").textContent =
      "Draft " + result.draft_id + " saved privately. Review before publishing.";
  } catch (error) {
    if (revision === contextRevision) {
      get("draft-message").textContent = "Draft not confirmed: " + error.message + ". Re-submit unchanged fields to retry safely.";
    }
  } finally {
    creating = false;
    button.disabled = false;
  }
});

get("preview-button").addEventListener("click", async () => {
  const question = get("preview-question").value.trim();
  if (!question) {
    get("preview-result").textContent = "Enter a question first.";
    return;
  }
  const revision = contextRevision;
  const property = get("property").value;
  const button = get("preview-button");
  button.disabled = true;
  get("preview-result").textContent = "Checking currently approved public facts...";
  try {
    const response = await fetch(
      "/api/properties/" + encodeURIComponent(property) + "/information",
      {method: "POST", headers: {"Content-Type": "application/json"},
       body: JSON.stringify({question}), cache: "no-store"}
    );
    const data = await response.json().catch(() => ({}));
    if (revision !== contextRevision) return;
    if (!response.ok) throw Error("Public FAQ is unavailable.");
    get("preview-result").textContent = data.status === "answered"
      ? data.answer + " (Local approved version " + data.version + ", source: " + data.source + "; no AI model.)"
      : "No approved answer found. The guest should use the direct human enquiry form.";
  } catch (error) {
    if (revision === contextRevision) get("preview-result").textContent = "FAQ unavailable. Use direct human enquiry.";
  } finally {
    button.disabled = false;
  }
});

get("load-knowledge").addEventListener("click", loadKnowledge);
get("property").addEventListener("change", () => {
  get("staff-key").value = "";
  get("staff-key").type = "password";
  get("show-key").textContent = "Show";
  get("show-key").setAttribute("aria-pressed", "false");
  resetKnowledge("Hotel changed. Enter its own development key and load.");
});
get("staff-key").addEventListener("input", () =>
  resetKnowledge("Staff key changed. Reload this hotel's records."));
get("show-key").addEventListener("click", () => {
  const field = get("staff-key");
  const reveal = field.type === "password";
  field.type = reveal ? "text" : "password";
  get("show-key").textContent = reveal ? "Hide" : "Show";
  get("show-key").setAttribute("aria-pressed", String(reveal));
  get("show-key").setAttribute("aria-label", reveal ? "Hide development key" : "Show development key");
});
