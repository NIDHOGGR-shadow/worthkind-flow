"use strict";
// Local-only hotel operations overview; never uses invented preview KPIs.
const byId = (id) => document.getElementById(id);
const create = (tag, value, className) => {
  const node = document.createElement(tag);
  if (value !== undefined) node.textContent = String(value);
  if (className) node.className = className;
  return node;
};
let revision = 0;

const KPI_KEYS = [
  "metric-case-total", "metric-case-queued", "metric-case-claimed",
  "metric-case-responded", "metric-ticket-total", "metric-ticket-unresolved",
  "metric-ticket-overdue", "metric-outbox-pending"
];
function statusMessage(value) {
  byId("overview-message").textContent = value;
}
function clearOverview(message = "Property context changed. Reauthorize to load the selected hotel.") {
  revision += 1;
  byId("overview-results").hidden = true;
  byId("overview-load").disabled = false;
  for (const id of KPI_KEYS) byId(id).textContent = "—";
  byId("overview-cases").replaceChildren();
  byId("overview-tickets").replaceChildren();
  byId("overview-hotel-name").textContent = "No property selected";
  byId("overview-source").textContent = "Source not loaded";
  statusMessage(message);
}
function isCount(value) {
  return Number.isSafeInteger(value) && value >= 0;
}
function validateSnapshot(data, slug) {
  if (!data || data.source !== "property_scoped_local_sqlite" ||
      data.data_is_synthetic !== true || data.production_ready !== false ||
      data.property?.slug !== slug ||
      !Array.isArray(data.cases?.recent) || !Array.isArray(data.tickets?.recent)) {
    throw new Error("Unexpected local overview response.");
  }
  const nums = [
    data.cases.total, data.cases.by_status?.queued,
    data.cases.by_status?.claimed, data.cases.by_status?.responded,
    data.tickets.total, data.tickets.unresolved, data.tickets.overdue,
    data.local_outbox?.pending_total
  ];
  if (!nums.every(isCount)) throw new Error("Invalid overview count.");
  return nums;
}
function appendActivity(root, recent, what) {
  root.replaceChildren();
  if (!recent.length) {
    root.append(create("p", "No " + what + " recorded for this demo property.", "case-empty"));
    return;
  }
  for (const row of recent) {
    const item = create("article", undefined, "overview-activity-item");
    item.setAttribute("role", "listitem");
    const top = create("div", undefined, "overview-activity-top");
    const category = row.kind || row.category || "general";
    const name = what === "enquiries" ? "Guest " + category : "Team " + category;
    top.append(create("strong", name));
    const state = create("span", row.status || "unknown", "status-pill " + (row.status || ""));
    top.append(state);
    item.append(top);
    if (what === "tickets") {
      item.append(create("small", "Priority: " + (row.priority || "unknown") + " · Local due: " + (row.due_at || "unspecified")));
    } else {
      item.append(create("small", "Case reference: " + (row.id || "unavailable")));
    }
    root.append(item);
  }
}
async function loadOverview() {
  const key = byId("overview-key").value;
  const slug = byId("overview-property").value;
  if (!key.trim()) {
    clearOverview("Enter the development staff key to load this hotel's local records.");
    return;
  }
  const requestRevision = ++revision;
  const button = byId("overview-load");
  button.disabled = true;
  byId("overview-results").hidden = true;
  statusMessage("Loading actual local SQLite records...");
  try {
    const response = await fetch(
      "/api/properties/" + encodeURIComponent(slug) + "/staff/overview",
      {headers: {"X-Staff-Key": key}, cache: "no-store"}
    );
    const result = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error("Authorization failed or local server unavailable.");
    const counts = validateSnapshot(result, slug);
    if (requestRevision !== revision) return; // No stale cross-property data.
    KPI_KEYS.forEach((id, index) => {
      byId(id).textContent = String(counts[index]);
    });
    byId("overview-hotel-name").textContent = result.property.name;
    const updated = new Date(result.as_of);
    byId("overview-source").textContent =
      "Source: local property-scoped SQLite · " +
      (Number.isNaN(updated.getTime()) ? "Refresh time unavailable" : updated.toLocaleString()) +
      " · No external integrations";
    appendActivity(byId("overview-cases"), result.cases.recent, "enquiries");
    appendActivity(byId("overview-tickets"), result.tickets.recent, "tickets");
    byId("overview-results").hidden = false;
    statusMessage("Local records loaded for " + result.property.name + ". All counts are from SQLite.");
  } catch (error) {
    if (requestRevision !== revision) return;
    clearOverview("Unable to load this property's records. Check your local key and connection.");
  } finally {
    if (requestRevision === revision) button.disabled = false;
  }
}
byId("overview-load").addEventListener("click", loadOverview);
byId("overview-property").addEventListener("change", () => {
  clearOverview("Demo hotel changed. Load its records with that hotel's key.");
});
byId("overview-key").addEventListener("input", () => {
  clearOverview("Development key changed. Verify your access again.");
});
byId("overview-key-toggle").addEventListener("click", () => {
  const key = byId("overview-key");
  const showing = key.type === "password";
  key.type = showing ? "text" : "password";
  byId("overview-key-toggle").textContent = showing ? "Hide" : "Show";
  byId("overview-key-toggle").setAttribute(
    "aria-label", showing ? "Hide development staff key" : "Show development staff key"
  );
  byId("overview-key-toggle").setAttribute("aria-pressed", String(showing));
});
