"use strict";
// Development dashboard: every displayed count comes from property-scoped SQLite.
const byId = (id) => document.getElementById(id);
const node = (tag, value, className) => {
  const item = document.createElement(tag);
  if (value !== undefined) item.textContent = value;
  if (className) item.className = className;
  return item;
};
let revision = 0;

function scrubOverview() {
  // Hide AND remove stale hotel metrics from the DOM on context changes.
  byId("overview").hidden = true;
  byId("overview-empty").hidden = false;
  for (const id of [
    "case-total", "case-queued", "case-responded", "ticket-unresolved",
    "ticket-overdue", "events-pending", "property-name", "generated-at", "invalid-due"
  ]) byId(id).textContent = "—";
  for (const id of [
    "case-statuses", "case-kinds", "ticket-statuses", "ticket-categories",
    "event-counts", "activity-list", "attention-list"
  ]) byId(id).replaceChildren();
  byId("attention-message").textContent = "No deadline queue loaded.";
  byId("attention-load").disabled = false;
}

function resetOverview(note) {
  revision += 1;
  scrubOverview();
  byId("load-overview").disabled = false;
  byId("message").textContent = note;
}

function safeCount(value) {
  if (!Number.isSafeInteger(value) || value < 0) {
    throw Error("Unexpected metric returned by the development API.");
  }
  return String(value);
}

function rows(id, records, emptyMessage) {
  const root = byId(id);
  root.replaceChildren();
  const entries = Object.entries(records || {});
  if (!entries.length) {
    root.append(node("p", emptyMessage, "workspace-subtitle"));
    return;
  }
  for (const [label, value] of entries) {
    const line = node("div", undefined, "ops-data-row");
    line.append(node("span", label.replaceAll("_", " ")), node("strong", safeCount(value)));
    root.append(line);
  }
}

function showOverview(data) {
  if (data?.source !== "local_sqlite_development" || !data.case_counts ||
      !data.ticket_counts || !data.local_events ||
      data.local_events.provider_delivery_connected !== false ||
      data.local_events.delivery_confirmed !== false) {
    throw Error("Unavailable or unverified development data source.");
  }
  const counts = [
    ["case-total", data.case_counts.total],
    ["case-queued", data.case_counts.by_status.queued],
    ["case-responded", data.case_counts.by_status.responded],
    ["ticket-unresolved", data.ticket_counts.unresolved],
    ["ticket-overdue", data.ticket_counts.overdue],
    ["events-pending", data.local_events.pending_total]
  ];
  // Validate everything before publishing a partially updated view.
  for (const [, value] of counts) safeCount(value);
  safeCount(data.ticket_counts.invalid_due_dates);
  safeCount(data.local_events.pending_case_events);
  safeCount(data.local_events.pending_ticket_events);
  for (const [id, value] of counts) byId(id).textContent = String(value);

  byId("property-name").textContent = data.property.display_name;
  const generated = new Date(data.generated_at);
  byId("generated-at").textContent = Number.isNaN(generated.valueOf())
    ? "Update time unavailable"
    : "Snapshot: " + generated.toLocaleString();

  rows("case-statuses", data.case_counts.by_status, "No enquiries.");
  rows("case-kinds", data.case_counts.by_kind, "No categories recorded.");
  rows("ticket-statuses", data.ticket_counts.by_status, "No tickets.");
  rows("ticket-categories", data.ticket_counts.by_category, "No departments recorded.");
  rows("event-counts", {
    case_events_pending: data.local_events.pending_case_events,
    ticket_events_pending: data.local_events.pending_ticket_events
  }, "No pending local events.");

  byId("invalid-due").textContent = data.ticket_counts.invalid_due_dates
    ? safeCount(data.ticket_counts.invalid_due_dates) + " tickets have invalid due dates and are excluded from overdue counts."
    : "";

  const activity = byId("activity-list");
  activity.replaceChildren();
  if (!Array.isArray(data.recent_activity)) throw Error("Unexpected activity response.");
  if (!data.recent_activity.length) {
    activity.append(node("p", "No local activity recorded.", "workspace-subtitle"));
  } else {
    for (const event of data.recent_activity) {
      const line = node("div", undefined, "ops-activity-row");
      const label = event.type === "service_ticket" ? "Ticket" : "Enquiry";
      const heading = node("strong", label + " · " + String(event.action || "").replaceAll("_", " "));
      const details = node("span", "Ref: " + String(event.reference || ""));
      const stamp = new Date(event.occurred_at);
      const time = node("time", Number.isNaN(stamp.valueOf()) ? "Date unavailable" : stamp.toLocaleString());
      line.append(heading, details, time);
      activity.append(line);
    }
  }
  byId("overview-empty").hidden = true;
  byId("overview").hidden = false;
}

async function loadOverview() {
  const key = byId("staff-key").value;
  const property = byId("property").value;
  if (!key.trim()) {
    resetOverview("Enter this hotel's local development staff key.");
    return;
  }
  const requestRevision = ++revision;
  scrubOverview();
  byId("load-overview").disabled = true;
  byId("message").textContent = "Reading current local SQLite records...";
  try {
    const response = await fetch(
      "/api/properties/" + encodeURIComponent(property) + "/staff/operations/overview",
      {headers: {"X-Staff-Key": key}, cache: "no-store"}
    );
    const data = await response.json().catch(() => ({}));
    if (requestRevision !== revision) return;
    if (!response.ok) throw Error("Access denied or local API unavailable.");
    if (data.property?.slug !== property) throw Error("Unexpected property response.");
    showOverview(data);
    byId("message").textContent = "Loaded current " + property + " SQLite records. No live external systems connected.";
  } catch (error) {
    if (requestRevision !== revision) return;
    scrubOverview();
    byId("message").textContent = "Could not load this hotel's local operational data. " + error.message;
  } finally {
    if (requestRevision === revision) byId("load-overview").disabled = false;
  }
}

function displayAttention(data, property) {
  if (data.property !== property || data.source !== "local_sqlite_development" ||
      data.provider_connected !== false || data.alerts_sent !== 0 ||
      !Array.isArray(data.items)) {
    throw Error("Unverified development deadline response.");
  }
  const count = safeCount(data.actionable_total);
  const container = byId("attention-list");
  container.replaceChildren();
  if (data.items.length === 0) {
    container.append(node("p", "No overdue, due-soon or invalid-date tickets.", "workspace-subtitle"));
  } else {
    for (const item of data.items) {
      const card = node("article", undefined, "ops-activity-row");
      const classification = item.attention === "invalid_due"
        ? "Invalid deadline—check source"
        : item.attention === "overdue" ? "Overdue" : "Due soon";
      card.append(
        node("strong", classification + " · " + String(item.subject || "Untitled ticket")),
        node("span", String(item.category || "General") + " · " +
          String(item.priority || "Unspecified") + " · " +
          String(item.status || "Unknown")),
        node("span", "Ticket: " + String(item.ticket_id || "Unknown") +
          " · Due: " + String(item.due_at || "Unavailable"))
      );
      container.append(card);
    }
  }
  byId("attention-message").textContent = count +
    " ticket(s) need human review. This queue has not sent any alerts.";
}

async function loadAttention() {
  if (byId("overview").hidden) {
    byId("attention-message").textContent = "Load the hotel's overview before reviewing its deadlines.";
    return;
  }
  const currentRevision = revision;
  const property = byId("property").value;
  const key = byId("staff-key").value;
  const button = byId("attention-load");
  button.disabled = true;
  byId("attention-message").textContent = "Checking the selected hotel's current SQLite deadlines...";
  try {
    const response = await fetch(
      "/api/properties/" + encodeURIComponent(property) + "/staff/operations/attention",
      {headers: {"X-Staff-Key": key}, cache: "no-store"}
    );
    const body = await response.json().catch(() => ({}));
    if (currentRevision !== revision) return;
    if (!response.ok) throw Error("Ticket attention data is unavailable.");
    displayAttention(body, property);
  } catch (error) {
    if (currentRevision !== revision) return;
    byId("attention-list").replaceChildren();
    byId("attention-message").textContent = "Could not verify the local ticket queue: " + error.message;
  } finally {
    if (currentRevision === revision) button.disabled = false;
  }
}

byId("load-overview").addEventListener("click", loadOverview);
byId("attention-load").addEventListener("click", loadAttention);
byId("property").addEventListener("change", () => {
  byId("staff-key").value = "";
  byId("staff-key").type = "password";
  byId("show-key").textContent = "Show";
  byId("show-key").setAttribute("aria-pressed", "false");
  resetOverview("Hotel changed. Enter its correct key and reload.");
});
byId("staff-key").addEventListener("input", () => resetOverview("Staff key changed. Reload to verify access."));
byId("show-key").addEventListener("click", () => {
  const input = byId("staff-key");
  const reveal = input.type === "password";
  input.type = reveal ? "text" : "password";
  byId("show-key").textContent = reveal ? "Hide" : "Show";
  byId("show-key").setAttribute("aria-label", reveal ? "Hide development staff key" : "Show development staff key");
  byId("show-key").setAttribute("aria-pressed", String(reveal));
});
