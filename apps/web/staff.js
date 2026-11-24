"use strict";
// Development-only reception UI. Real counts come from the property-scoped API.
// Rendering guest content uses textContent, never HTML injection.
const byId = (id) => document.getElementById(id);
const element = (tag, text, className) => {
  const node = document.createElement(tag);
  if (text !== undefined) node.textContent = text;
  if (className) node.className = className;
  return node;
};
const state = { cases: [], loaded: false, revision: 0 };
const statusNames = { queued: "Queued", claimed: "Claimed", responded: "Responded" };

function message(text) {
  byId("message").textContent = text;
}

async function action(url, method = "GET", payload, staffKey = byId("key").value) {
  const headers = { "X-Staff-Key": staffKey };
  if (payload !== undefined) headers["Content-Type"] = "application/json";
  const response = await fetch(url, {
    method, headers, cache: "no-store",
    body: payload === undefined ? undefined : JSON.stringify(payload)
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(typeof data.detail === "string" ? data.detail : "Request unavailable. Retry or contact your supervisor.");
  }
  return data;
}

function updateCounters() {
  for (const [status, id] of [
    ["all", "total-cases"],
    ["queued", "queued-cases"],
    ["claimed", "claimed-cases"],
    ["responded", "responded-cases"]
  ]) {
    byId(id).textContent = state.loaded
      ? String(status === "all" ? state.cases.length : state.cases.filter((item) => item.status === status).length)
      : "—";
  }
}

function emptyCard(text) {
  return element("div", text, "case-empty");
}

const ticketRequests = new Map();

function freshTicketRequest(item, payload) {
  // Retain the same idempotency key on a lost POST response.
  const snapshot = JSON.stringify({
    property: byId("p").value, source_case_id: item.id, ...payload
  });
  const prior = ticketRequests.get(item.id);
  if (!prior || prior.snapshot !== snapshot) {
    if (!globalThis.crypto?.getRandomValues) {
      throw Error("Secure random generation unavailable; use localhost or HTTPS.");
    }
    const bytes = crypto.getRandomValues(new Uint8Array(16));
    const key = Array.from(bytes, value => value.toString(16).padStart(2, "0")).join("");
    ticketRequests.set(item.id, { snapshot, key });
  }
  return { ...payload, request_key: ticketRequests.get(item.id).key };
}

function linkedTicketControl(item) {
  const region = element("section", undefined, "case-ticket-handoff");
  region.append(element("h4", "Department handoff"));

  if (item.linked_ticket_id) {
    region.append(
      element("p", "Linked ticket: " + item.linked_ticket_id +
        " · Status: " + (item.linked_ticket_status || "unknown"), "workspace-tip")
    );
    const jump = element("a", "Open department tickets", "button secondary compact");
    jump.href = "/staff/tickets";
    region.append(jump);
    return region;
  }

  const form = element("form", undefined, "case-ticket-form");
  const categoryId = "ticket-category-" + item.id;
  const categoryLabel = element("label", "Department");
  categoryLabel.htmlFor = categoryId;
  const category = element("select");
  category.id = categoryId;
  for (const value of [
    "general", "reception", "housekeeping", "maintenance",
    "it", "kitchen", "billing"
  ]) {
    const option = element("option", value === "it" ? "IT" : value);
    option.value = value;
    category.append(option);
  }
  category.value = item.kind === "food" ? "kitchen" :
    item.kind === "booking" || item.kind === "human" ? "reception" : "general";

  const priorityId = "ticket-priority-" + item.id;
  const priorityLabel = element("label", "Priority");
  priorityLabel.htmlFor = priorityId;
  const priority = element("select");
  priority.id = priorityId;
  for (const value of ["normal", "low", "high", "urgent"]) {
    const option = element("option", value);
    option.value = value;
    priority.append(option);
  }
  priority.value = "normal";

  const titleId = "ticket-subject-" + item.id;
  const titleLabel = element("label", "Department task title");
  titleLabel.htmlFor = titleId;
  const title = element("input");
  title.id = titleId;
  title.type = "text";
  title.minLength = 4;
  title.maxLength = 160;
  title.required = true;
  title.placeholder = "e.g. Inspect room air conditioning";

  const detailId = "ticket-detail-" + item.id;
  const detailLabel = element("label", "What should the department do?");
  detailLabel.htmlFor = detailId;
  const detail = element("textarea");
  detail.id = detailId;
  detail.rows = 3;
  detail.minLength = 8;
  detail.maxLength = 3000;
  detail.required = true;
  detail.placeholder = "Explain the assigned work without copying guest contact details.";

  const button = element("button", "Create linked department ticket", "button secondary");
  button.type = "submit";
  form.append(
    categoryLabel, category, priorityLabel, priority,
    titleLabel, title, detailLabel, detail, button
  );
  form.addEventListener("submit", async event => {
    event.preventDefault();
    const subject = title.value.trim();
    const description = detail.value.trim();
    if (subject.length < 4 || description.length < 8) {
      message("Use a task title of at least 4 characters and a description of at least 8.");
      return;
    }
    const revision = state.revision;
    const key = byId("key").value;
    let body;
    try {
      body = freshTicketRequest(item, {
        origin_case_id: item.id,
        category: category.value,
        priority: priority.value,
        subject, description
      });
    } catch (error) {
      message(error.message);
      return;
    }
    button.disabled = true;
    message("Recording department handoff in local SQLite...");
    try {
      const url = "/api/properties/" + encodeURIComponent(byId("p").value) + "/staff/tickets";
      await action(url, "POST", body, key);
      if (revision !== state.revision) return;
      ticketRequests.delete(item.id);
      await loadCases(); // Verify the ticket was actually linked by the local API.
      message("Linked department ticket recorded locally. No external message has been sent.");
    } catch (error) {
      if (revision === state.revision) {
        message("Department handoff not confirmed: " + error.message +
          ". Retry unchanged details to reuse the same request key.");
      }
    } finally {
      button.disabled = false;
    }
  });
  region.append(
    element("p", "Create internal follow-up work only after reception accepts this enquiry. Not a hotel booking or message.", "workspace-tip"),
    form
  );
  return region;
}

function renderCases() {
  updateCounters();
  const root = byId("cases");
  root.replaceChildren();

  if (!state.loaded) {
    byId("visible-count").textContent = "No cases loaded";
    root.append(emptyCard("Load a demo property's cases to see the staff queue."));
    return;
  }

  const filter = byId("filter-status").value;
  const query = byId("search-cases").value.trim().toLocaleLowerCase();
  const cases = state.cases.filter((item) => {
    if (filter !== "all" && item.status !== filter) return false;
    const searchText = [item.customer_name, item.kind, item.details, item.staff_reply]
      .filter(Boolean).join(" ").toLocaleLowerCase();
    return searchText.includes(query);
  });
  byId("visible-count").textContent =
    String(cases.length) + " of " + String(state.cases.length) + " loaded cases";

  if (!cases.length) {
    root.append(emptyCard("No matching cases. Change the filters or load the queue again."));
    return;
  }

  for (const item of cases) {
    const card = element("article", undefined, "case-card");
    card.setAttribute("role", "listitem");
    const heading = element("div", undefined, "case-card-head");
    const headingText = element("div");
    headingText.append(
      element("span", String(item.kind || "general"), "case-topic"),
      element("h3", item.customer_name || "Guest enquiry")
    );
    const status = Object.hasOwn(statusNames, item.status) ? item.status : "unknown";
    heading.append(
      headingText,
      element("span", statusNames[status] || "Unknown", "status-pill " + status)
    );
    card.append(heading, element("p", item.details || "No details supplied.", "case-detail"));

    if (item.staff_reply) {
      const reply = element("p", undefined, "case-reply");
      reply.append(element("strong", "Recorded staff reply: "), element("span", item.staff_reply));
      card.append(reply);
    }

    const base = "/api/properties/" + encodeURIComponent(byId("p").value) +
      "/staff/enquiries/" + encodeURIComponent(item.id);

    if (item.status === "queued") {
      const actions = element("div", undefined, "case-actions");
      const claim = element("button", "Claim this case", "button primary");
      claim.type = "button";
      claim.addEventListener("click", () => runMutation(claim, base + "/claim"));
      actions.append(claim);
      card.append(actions);
    } else if (item.status === "claimed") {
      const form = element("form", undefined, "case-reply-form");
      const label = element("label", "Reply to this guest");
      const input = element("textarea");
      const inputId = "reply-" + item.id;
      input.id = inputId;
      input.rows = 3;
      input.minLength = 2;
      input.maxLength = 3000;
      input.required = true;
      input.placeholder = "Write an accurate staff response. This does not confirm a booking or payment.";
      label.htmlFor = inputId;
      const button = element("button", "Record response", "button primary");
      button.type = "submit";
      const actions = element("div", undefined, "case-actions");
      actions.append(button);
      form.append(label, input, actions);
      form.addEventListener("submit", async (event) => {
        event.preventDefault();
        const answer = input.value.trim();
        if (answer.length < 2) {
          message("Write at least two characters before recording a response.");
          input.focus();
          return;
        }
        await runMutation(button, base + "/respond", { message: answer });
      });
      card.append(form);
    }
    if (item.status === "claimed" || item.status === "responded") {
      card.append(linkedTicketControl(item));
    }
    root.append(card);
  }
}

function clearCases(reason) {
  // Clears private request content if property or credential changes during a fetch.
  state.revision += 1;
  state.cases = [];
  state.loaded = false;
  ticketRequests.clear();
  byId("load").disabled = false;
  renderCases();
  message(reason);
}

async function loadCases() {
  const slug = byId("p").value;
  const key = byId("key").value;
  if (!key.trim()) {
    clearCases("Enter the development staff key before loading the selected property's cases.");
    return;
  }

  const requestRevision = ++state.revision;
  byId("load").disabled = true;
  message("Loading this property's cases...");
  try {
    const base = "/api/properties/" + encodeURIComponent(slug) + "/staff/enquiries";
    const result = await action(base, "GET", undefined, key);
    if (requestRevision !== state.revision) return; // Property/key changed while loading.
    if (!Array.isArray(result.cases)) throw new Error("Unexpected case list response.");
    state.cases = result.cases;
    state.loaded = true;
    renderCases();
    message(result.cases.length
      ? "Cases loaded. Claim a queued request or record a response for a claimed one."
      : "No enquiries for this demo property yet.");
  } catch (error) {
    if (requestRevision !== state.revision) return;
    state.cases = [];
    state.loaded = false;
    renderCases();
    message("Unable to load cases: " + error.message);
  } finally {
    if (requestRevision === state.revision) byId("load").disabled = false;
  }
}

async function runMutation(button, url, payload) {
  const requestRevision = state.revision;
  const key = byId("key").value;
  button.disabled = true; // Prevent accidental duplicate clicks.
  message("Saving the staff action...");
  try {
    await action(url, "POST", payload, key);
    if (requestRevision !== state.revision) return;
    await loadCases(); // Refresh from authoritative development API, not a guessed state.
  } catch (error) {
    if (requestRevision !== state.revision) return;
    message("Action not confirmed: " + error.message + ". Refresh before retrying.");
    button.disabled = false;
  }
}

byId("load").addEventListener("click", loadCases);
byId("p").addEventListener("change", () => clearCases("Property changed. Load its cases using the correct key."));
byId("key").addEventListener("input", () => clearCases("Key changed. Load cases again to confirm access."));
byId("filter-status").addEventListener("change", renderCases);
byId("search-cases").addEventListener("input", renderCases);
byId("toggle-key").addEventListener("click", () => {
  const input = byId("key");
  const showing = input.type === "password";
  input.type = showing ? "text" : "password";
  byId("toggle-key").textContent = showing ? "Hide" : "Show";
  byId("toggle-key").setAttribute("aria-label", showing ? "Hide development staff key" : "Show development staff key");
  byId("toggle-key").setAttribute("aria-pressed", String(showing));
});
