"use strict";
const { test } = require("node:test");
const assert = require("node:assert/strict");
const { webcrypto } = require("node:crypto");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

class Node {
  constructor(tag = "div") {
    this.tagName = tag.toUpperCase();
    this.children = []; this.handlers = {};
    this.value = ""; this.textContent = "";
    this.style = {}; this.hidden = false; this.disabled = false;
  }
  addEventListener(name, handler) { (this.handlers[name] ||= []).push(handler); }
  replaceChildren(...items) { this.children = items; }
  append(...items) { this.children.push(...items); }
  setAttribute() {}
  reportValidity() { return true; }
  async trigger(name) {
    await Promise.all((this.handlers[name] || []).map(fn =>
      fn({ preventDefault() {}, currentTarget: this })
    ));
  }
}
const flat = (node) => [node, ...node.children.flatMap(flat)];

function setup() {
  const ids = [
    "property", "staff-key", "status-filter", "category-filter", "ticket-list",
    "metrics", "connection-status", "form-status", "ticket-form", "create",
    "category", "priority", "subject", "description", "source-case",
    "refresh", "apply-filter"
  ];
  const nodes = Object.fromEntries(ids.map(id => [id, new Node()]));
  nodes.property.value = "demo-hotel";
  nodes["staff-key"].value = "staff-one";
  nodes.category.value = "it";
  nodes.priority.value = "normal";
  nodes.subject.value = "Synthetic IT problem";
  nodes.description.value = "Synthetic Wi-Fi outage at the reception desk";

  const records = {
    "demo-hotel": [{
      id: "one", subject: "Hotel A ticket", category: "it", priority: "normal",
      description: "Development-only ticket", status: "open",
      overdue: false, due_at: "2026-11-19T16:00:00Z", assigned_to: null
    }],
    "demo-hotel-two": [{
      id: "two", subject: "Hotel B ticket", category: "reception", priority: "high",
      description: "Second property only", status: "open",
      overdue: false, due_at: "2026-11-19T16:00:00Z", assigned_to: null
    }]
  };
  const pending = [];
  const server = { holdHotelA: false, requests: [], records, pending };
  const respond = (payload, status = 200) => ({ ok: status < 400, status, async json() { return payload; } });

  const fetch = async (url, options = {}) => {
    server.requests.push({ url, options });
    const hotel = url.includes("/demo-hotel-two/") ? "demo-hotel-two" : "demo-hotel";
    const key = hotel === "demo-hotel" ? "staff-one" : "staff-two";
    if (options.headers["X-Staff-Key"] !== key) {
      return respond({ detail: "Development staff authentication required" }, 401);
    }
    const payload = options.method === "POST"
      ? (() => {
        const item = JSON.parse(options.body);
        const created = {
          id: "new-" + (records[hotel].length + 1),
          subject: item.subject, category: item.category, priority: item.priority,
          description: item.description, status: "open", assigned_to: null,
          due_at: "2026-11-19T16:00:00Z", overdue: false
        };
        records[hotel].push(created);
        return { ticket_id: created.id, status: "open", duplicate: false };
      })()
      : url.includes("/metrics")
        ? { total: records[hotel].length, unresolved: records[hotel].length,
            overdue: 0, by_status: { resolved: 0 } }
        : { tickets: records[hotel] };

    if (server.holdHotelA && hotel === "demo-hotel") {
      return new Promise(resolve => pending.push(() => resolve(respond(payload))));
    }
    return respond(payload, options.method === "POST" ? 201 : 200);
  };

  const source = fs.readFileSync(path.join(__dirname, "../tickets.js"), "utf8");
  vm.runInNewContext(source, {
    document: {
      getElementById(id) {
        assert.ok(nodes[id], "Unknown element " + id);
        return nodes[id];
      },
      createElement(tag) { return new Node(tag); }
    },
    fetch, crypto: webcrypto, URLSearchParams, encodeURIComponent, Date, Error, Set
  }, { filename: "tickets.js" });
  return { nodes, server };
}

test("local ticket UI shows only current property data from the simulated local API", async () => {
  const { nodes, server } = setup();
  await nodes.refresh.trigger("click");
  assert.ok(flat(nodes["ticket-list"]).some(n => n.textContent === "Hotel A ticket"));
  assert.ok(!flat(nodes["ticket-list"]).some(n => n.textContent === "Hotel B ticket"));
  assert.equal(nodes.metrics.children.length, 4);
  assert.equal(server.requests[0].options.cache, "no-store");

  nodes.property.value = "demo-hotel-two";
  nodes["staff-key"].value = "staff-two";
  await nodes.property.trigger("change");
  assert.equal(nodes["ticket-list"].children.length, 0);
  assert.equal(nodes.metrics.children.length, 0);
  await nodes.refresh.trigger("click");
  assert.ok(flat(nodes["ticket-list"]).some(n => n.textContent === "Hotel B ticket"));
  assert.ok(!flat(nodes["ticket-list"]).some(n => n.textContent === "Hotel A ticket"));
});

test("an in-flight response cannot repopulate another hotel's workspace", async () => {
  const { nodes, server } = setup();
  server.holdHotelA = true;
  const first = nodes.refresh.trigger("click");
  assert.equal(server.pending.length, 2);
  nodes.property.value = "demo-hotel-two";
  nodes["staff-key"].value = "staff-two";
  await nodes.property.trigger("change");
  server.pending.forEach(done => done());
  await first;
  assert.equal(nodes.metrics.children.length, 0);
  assert.equal(nodes["ticket-list"].children.length, 0);
  await nodes.refresh.trigger("click");
  assert.ok(flat(nodes["ticket-list"]).some(n => n.textContent === "Hotel B ticket"));
});

test("changing credentials clears all ticket data and sensitive counts", async () => {
  const { nodes } = setup();
  await nodes.refresh.trigger("click");
  assert.equal(nodes.metrics.children.length, 4);
  nodes["staff-key"].value = "wrong-secret";
  await nodes["staff-key"].trigger("input");
  assert.equal(nodes.metrics.children.length, 0);
  assert.equal(nodes["ticket-list"].children.length, 0);
  await nodes.refresh.trigger("click");
  assert.match(nodes["connection-status"].textContent, /Unable to load tickets/);
});

test("ticket creation uses local API and refreshes real returned data", async () => {
  const { nodes, server } = setup();
  await nodes["ticket-form"].trigger("submit");
  assert.equal(server.records["demo-hotel"].length, 2);
  assert.equal(nodes.create.disabled, false);
  assert.match(nodes["form-status"].textContent, /Ticket new-2 created as open/);
  assert.ok(flat(nodes["ticket-list"]).some(n => n.textContent === "Synthetic IT problem"));
  const post = server.requests.find(req => req.options.method === "POST");
  assert.ok(post && JSON.parse(post.options.body).request_key.length >= 8);
});
