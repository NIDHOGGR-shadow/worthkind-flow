"use strict";
// Real local API readiness, never browser-stored keys or invented provider statuses.
const el = id => document.getElementById(id);
const build = (tag, text, className) => {
  const item = document.createElement(tag);
  if (text !== undefined) item.textContent = text;
  if (className) item.className = className;
  return item;
};
let revision = 0;

function scrub(message) {
  revision++;
  el("readiness-content").hidden = true;
  el("readiness-empty").hidden = false;
  el("readiness-property").textContent = "—";
  el("readiness-source").textContent = "—";
  el("authority").textContent = "No source checked.";
  el("providers").replaceChildren();
  el("connection-message").textContent = message;
  el("load-readiness").disabled = false;
}

function display(data, requestedProperty) {
  const expectedServices = new Set([
    "pms_availability", "pms_reservation", "hotel_payment", "guest_messaging", "optional_ai"
  ]);
  const services = data?.services;
  if (data?.property !== requestedProperty ||
      data.source !== "disabled_development_adapters" ||
      data.production_connected !== false ||
      data.live_bookings !== false || data.live_payments !== false ||
      data.live_messages !== false || data.live_ai !== false ||
      !Array.isArray(services) || services.length !== expectedServices.size) {
    throw Error("Integration status has unverified provenance.");
  }
  for (const service of services) {
    if (!expectedServices.delete(service.service) ||
        service.configured !== false || service.authoritative !== false ||
        service.mode !== "disabled" || typeof service.description !== "string") {
      throw Error("Unexpected adapter authority. Verification required before display.");
    }
  }
  if (expectedServices.size) throw Error("Missing integration capabilities.");

  const root = el("providers");
  root.replaceChildren();
  for (const service of services) {
    const card = build("article", undefined, "knowledge-card");
    card.append(build("strong", service.service.replaceAll("_", " ")));
    card.append(build("p", "Not connected · Not authoritative", "ops-warning"));
    card.append(build("p", service.description, "workspace-subtitle"));
    root.append(card);
  }
  el("readiness-property").textContent = requestedProperty;
  el("readiness-source").textContent = "Source: disabled development adapters";
  el("authority").textContent =
    "No authorized PMS, payment, communications or AI provider is connected. No booking, payment or delivery is confirmed.";
  el("readiness-empty").hidden = true;
  el("readiness-content").hidden = false;
}

async function loadReadiness() {
  const property = el("property").value;
  const key = el("staff-key").value;
  if (!key.trim()) {
    scrub("Enter this property's development key before checking integration status.");
    return;
  }
  scrub("Checking this hotel's local provider contracts...");
  const current = revision;
  el("load-readiness").disabled = true;
  try {
    const response = await fetch(
      "/api/properties/" + encodeURIComponent(property) + "/staff/integrations/readiness",
      {headers: {"X-Staff-Key": key}, cache: "no-store"}
    );
    const data = await response.json().catch(() => ({}));
    if (current !== revision) return;
    if (!response.ok) throw Error("Access denied or development API unavailable.");
    display(data, property);
    el("connection-message").textContent =
      "Integration readiness loaded from local web API. No live providers are enabled.";
  } catch (error) {
    if (current !== revision) return;
    scrub("Could not verify this hotel's integration status. " + error.message);
  } finally {
    if (current === revision) el("load-readiness").disabled = false;
  }
}

el("load-readiness").addEventListener("click", loadReadiness);
el("property").addEventListener("change", () => {
  el("staff-key").value = "";
  el("staff-key").type = "password";
  el("show-key").textContent = "Show";
  el("show-key").setAttribute("aria-pressed", "false");
  scrub("Hotel changed. Enter its correct development key.");
});
el("staff-key").addEventListener("input", () =>
  scrub("Development key changed. Reload this hotel's integration status."));
el("show-key").addEventListener("click", () => {
  const input = el("staff-key");
  const reveal = input.type === "password";
  input.type = reveal ? "text" : "password";
  el("show-key").textContent = reveal ? "Hide" : "Show";
  el("show-key").setAttribute("aria-pressed", String(reveal));
  el("show-key").setAttribute("aria-label", reveal ? "Hide development key" : "Show development key");
});
