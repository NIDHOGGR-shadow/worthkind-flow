"use strict";
const { test } = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

class FakeNode {
  constructor(tag = "div") {
    this.tagName = tag.toUpperCase();
    this.children = [];
    this.handlers = {};
    this.attributes = {};
    this.textContent = "";
    this.className = "";
    this.value = "";
    this.hidden = false;
    this.disabled = false;
    this.type = "";
  }
  addEventListener(name, handler) { (this.handlers[name] ||= []).push(handler); }
  setAttribute(name, value) { this.attributes[name] = String(value); }
  replaceChildren(...children) { this.children = children; }
  append(...children) { this.children.push(...children); }
  async trigger(name) {
    for (const listener of this.handlers[name] || []) {
      await listener({ preventDefault() {} });
    }
  }
}

const ids = [
  "property", "staff-key", "show-key", "load-overview", "message", "overview",
  "overview-empty", "property-name", "generated-at",
  "case-total", "case-queued", "case-responded", "ticket-unresolved",
  "ticket-overdue", "events-pending", "case-statuses", "case-kinds",
  "ticket-statuses", "ticket-categories", "event-counts", "invalid-due",
  "activity-list", "attention-list", "attention-message", "attention-load"
];

function syntheticSnapshot(slug, total) {
  return {
    property: { slug, display_name: slug === "demo-hotel" ? "Demo Hotel A" : "Demo Hotel B" },
    source: "local_sqlite_development",
    generated_at: "2026-11-19T18:00:00+00:00",
    case_counts: {
      total, by_status: { queued: total, claimed: 0, responded: 0 },
      by_kind: total ? { support: total } : {}
    },
    ticket_counts: {
      total: 2, unresolved: 1, overdue: 1, invalid_due_dates: 0,
      by_status: { open: 1, assigned: 0, in_progress: 0, resolved: 1, reopened: 0 },
      by_category: { maintenance: 2 }
    },
    local_events: {
      pending_total: total + 2, pending_case_events: total, pending_ticket_events: 2,
      provider_delivery_connected: false, delivery_confirmed: false
    },
    external_metrics: {
      confirmed_bookings: null, occupancy: null, hotel_revenue: null, agent_usage: null
    },
    recent_activity: [{
      reference: "<img src=x onerror=alert(1)>",
      action: "case_created",
      type: "guest_case",
      occurred_at: "2026-11-19T17:00:00+00:00"
    }]
  };
}

function rig(fetchImplementation) {
  const nodes = Object.fromEntries(ids.map(id => [id, new FakeNode()]));
  nodes.property.value = "demo-hotel";
  nodes["staff-key"].value = "hotel-a-key";
  nodes["staff-key"].type = "password";
  nodes.overview.hidden = true;
  const calls = [];
  const fetch = async (url, options) => {
    calls.push({ url, options });
    return fetchImplementation(url, options);
  };
  const source = fs.readFileSync(path.join(__dirname, "../operations.js"), "utf8");
  vm.runInNewContext(source, {
    document: {
      getElementById(id) {
        assert.ok(nodes[id], "Unexpected element: " + id);
        return nodes[id];
      },
      createElement(tag) { return new FakeNode(tag); }
    },
    fetch,
    encodeURIComponent,
    Error
  }, { filename: "operations.js" });
  return { nodes, calls };
}

function okJson(data, status = 200) {
  return {
    ok: status >= 200 && status < 300, status,
    async json() { return data; }
  };
}

test("renders API-sourced counts and safe event text, not static preview figures", async () => {
  const snapshot = syntheticSnapshot("demo-hotel", 7);
  const { nodes, calls } = rig(async () => okJson(snapshot));
  await nodes["load-overview"].trigger("click");

  assert.equal(nodes.overview.hidden, false);
  assert.equal(nodes["overview-empty"].hidden, true);
  assert.equal(nodes["case-total"].textContent, "7");
  assert.equal(nodes["case-queued"].textContent, "7");
  assert.equal(nodes["ticket-unresolved"].textContent, "1");
  assert.equal(nodes["ticket-overdue"].textContent, "1");
  assert.equal(nodes["events-pending"].textContent, "9");
  assert.equal(nodes["property-name"].textContent, "Demo Hotel A");
  assert.equal(calls[0].options.headers["X-Staff-Key"], "hotel-a-key");
  assert.equal(calls[0].options.cache, "no-store");
  assert.equal(nodes["activity-list"].children.length, 1);
  const refNode = nodes["activity-list"].children[0].children[1];
  assert.ok(refNode.textContent.includes("<img src=x"));
  assert.equal(refNode.children.length, 0); // no generated image / DOM HTML execution
});

test("changing the hotel clears private data and prevents stale in-flight responses", async () => {
  let resolveFetch;
  const pending = new Promise(resolve => { resolveFetch = resolve; });
  const { nodes, calls } = rig(async () => pending);
  const first = nodes["load-overview"].trigger("click");
  nodes.property.value = "demo-hotel-two";
  await nodes.property.trigger("change");
  assert.equal(nodes["staff-key"].value, "");
  assert.equal(nodes.overview.hidden, true);
  assert.equal(nodes["case-total"].textContent, "—");
  assert.equal(nodes["activity-list"].children.length, 0);
  resolveFetch(okJson(syntheticSnapshot("demo-hotel", 7)));
  await first;
  assert.equal(nodes.overview.hidden, true);
  assert.equal(nodes["case-total"].textContent, "—");
  assert.equal(calls.length, 1);

  nodes["staff-key"].value = "hotel-b-key";
  await nodes["staff-key"].trigger("input");
  // A fresh authenticated response may load the second hotel's data only.
});

test("changing the key scrubs a loaded view; 401 response never shows counts", async () => {
  const { nodes } = rig(async (url, options) =>
    options.headers["X-Staff-Key"] === "hotel-a-key"
      ? okJson(syntheticSnapshot("demo-hotel", 3))
      : okJson({ detail: "not authorized" }, 401)
  );
  await nodes["load-overview"].trigger("click");
  assert.equal(nodes["case-total"].textContent, "3");

  nodes["staff-key"].value = "wrong";
  await nodes["staff-key"].trigger("input");
  assert.equal(nodes.overview.hidden, true);
  assert.equal(nodes["case-total"].textContent, "—");
  assert.equal(nodes["case-statuses"].children.length, 0);
  await nodes["load-overview"].trigger("click");
  assert.equal(nodes.overview.hidden, true);
  assert.match(nodes.message.textContent, /Access denied/);
});

test("unknown or provider-connected metric provenance fails closed", async () => {
  const forged = syntheticSnapshot("demo-hotel", 9);
  forged.local_events.delivery_confirmed = true;
  const { nodes } = rig(async () => okJson(forged));
  await nodes["load-overview"].trigger("click");
  assert.equal(nodes.overview.hidden, true);
  assert.equal(nodes["case-total"].textContent, "—");
  assert.match(nodes.message.textContent, /unverified development data source/i);
});

test("development key show/hide is explicit and no key means no API request", async () => {
  const { nodes, calls } = rig(async () => okJson(syntheticSnapshot("demo-hotel", 1)));
  nodes["staff-key"].value = "";
  await nodes["load-overview"].trigger("click");
  assert.equal(calls.length, 0);
  assert.equal(nodes.overview.hidden, true);

  await nodes["show-key"].trigger("click");
  assert.equal(nodes["staff-key"].type, "text");
  assert.equal(nodes["show-key"].attributes["aria-pressed"], "true");
  await nodes["show-key"].trigger("click");
  assert.equal(nodes["staff-key"].type, "password");
  assert.equal(nodes["show-key"].attributes["aria-pressed"], "false");
});

test("SLA attention queue renders actual local ticket deadlines and never claims alerts sent", async () => {
  const { nodes, calls } = rig(async (url, options) => {
    if (url.endsWith("/operations/attention")) {
      return okJson({
        property: "demo-hotel", source: "local_sqlite_development",
        provider_connected: false, alerts_sent: 0, actionable_total: 1,
        items: [{
          ticket_id: "t-001", subject: "<img src=x onerror=alert(1)>",
          category: "maintenance", priority: "urgent", status: "open",
          due_at: "2026-11-20T13:00:00+00:00", attention: "overdue", minutes: 32
        }]
      });
    }
    return okJson(syntheticSnapshot("demo-hotel", 3));
  });
  await nodes["load-overview"].trigger("click");
  await nodes["attention-load"].trigger("click");
  assert.equal(nodes["attention-list"].children.length, 1);
  const row = nodes["attention-list"].children[0];
  assert.match(row.children[0].textContent, /<img src=x/);
  assert.equal(row.children[0].children.length, 0);
  assert.match(nodes["attention-message"].textContent, /has not sent any alerts/);
  assert.ok(calls.some(c => c.url.endsWith("/operations/attention")
    && c.options.cache === "no-store" && c.options.headers["X-Staff-Key"] === "hotel-a-key"));

  nodes.property.value = "demo-hotel-two";
  await nodes.property.trigger("change");
  assert.equal(nodes["attention-list"].children.length, 0);
  assert.equal(nodes["attention-message"].textContent, "No deadline queue loaded.");
});

test("SLA attention queue refuses data claiming provider alert delivery", async () => {
  const { nodes } = rig(async url => {
    if (url.endsWith("/operations/attention")) {
      return okJson({
        property: "demo-hotel", source: "local_sqlite_development",
        provider_connected: true, alerts_sent: 12,
        actionable_total: 1, items: [{ticket_id: "t-001"}]
      });
    }
    return okJson(syntheticSnapshot("demo-hotel", 1));
  });
  await nodes["load-overview"].trigger("click");
  await nodes["attention-load"].trigger("click");
  assert.equal(nodes["attention-list"].children.length, 0);
  assert.match(nodes["attention-message"].textContent, /Unverified development/);
});
