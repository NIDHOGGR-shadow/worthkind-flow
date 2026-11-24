"use strict";
const { test } = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const { webcrypto } = require("node:crypto");

// A tiny fake DOM permits behavior tests without a bundler or third-party jsdom.
class Node {
  constructor(tag = "div") {
    this.tagName = tag.toUpperCase();
    this.children = [];
    this.handlers = {};
    this.attributes = {};
    this.textContent = "";
    this.className = "";
    this.value = "";
    this.disabled = false;
    this.type = "";
  }
  addEventListener(name, handler) { (this.handlers[name] ||= []).push(handler); }
  append(...nodes) { this.children.push(...nodes); }
  replaceChildren(...nodes) { this.children = nodes; }
  setAttribute(name, value) { this.attributes[name] = String(value); }
  focus() {}
  async trigger(name) {
    for (const handler of this.handlers[name] || []) {
      await handler({ preventDefault() {} });
    }
  }
}

function descendants(node, predicate) {
  const result = [];
  for (const child of node.children) {
    if (predicate(child)) result.push(child);
    result.push(...descendants(child, predicate));
  }
  return result;
}

function rig({ failTicketReplyOnce = false } = {}) {
  const keys = [
    "p", "key", "toggle-key", "load", "filter-status", "search-cases",
    "total-cases", "queued-cases", "claimed-cases", "responded-cases",
    "visible-count", "message", "cases"
  ];
  const nodes = Object.fromEntries(keys.map((key) => [key, new Node()]));
  nodes.p.value = "demo-hotel";
  nodes.key.value = "staff-one";
  nodes.key.type = "password";
  nodes["filter-status"].value = "all";

  const database = {
    "demo-hotel": [
      { id: "q-1", kind: "booking", customer_name: "<img src=x>", details: "Room enquiry next Friday", status: "queued", staff_reply: null },
      { id: "q-2", kind: "human", customer_name: "Another Visitor", details: "Need reception", status: "claimed", staff_reply: null }
    ],
    "demo-hotel-two": [
      { id: "q-3", kind: "events", customer_name: "Other Property", details: "Conference enquiry", status: "queued", staff_reply: null }
    ]
  };
  const calls = [];
  const linkedTickets = new Map();

  const fetch = async (url, options = {}) => {
    calls.push({
      url, method: options.method, key: options.headers["X-Staff-Key"],
      cache: options.cache, body: options.body
    });
    const ticketPath = url.match(/^\/api\/properties\/([^/]+)\/staff\/tickets$/);
    if (ticketPath && options.method === "POST") {
      const slug = ticketPath[1];
      const requiredKey = slug === "demo-hotel" ? "staff-one" : "staff-two";
      const success = (payload, status = 200) => ({
        ok: status >= 200 && status < 300, status,
        async json() { return payload; }
      });
      if (options.headers["X-Staff-Key"] !== requiredKey) {
        return success({detail: "Staff authentication required"}, 401);
      }
      const body = JSON.parse(options.body);
      const item = database[slug].find(row => row.id === body.origin_case_id);
      if (!item || !["claimed", "responded"].includes(item.status)) {
        return success({detail: "Source enquiry must be claimed in this hotel"}, 409);
      }
      const stable = slug + ":" + body.request_key;
      let ticket = linkedTickets.get(stable);
      if (!ticket) {
        if (item.linked_ticket_id) return success({detail: "Case already linked"}, 409);
        ticket = {id: "ticket-for-" + item.id, ...body};
        linkedTickets.set(stable, ticket);
        item.linked_ticket_id = ticket.id;
        item.linked_ticket_status = "open";
      }
      if (failTicketReplyOnce) {
        failTicketReplyOnce = false;
        throw new Error("synthetic lost response after ticket creation");
      }
      return success({ticket_id: ticket.id, status: "open", duplicate: true}, 201);
    }
    const property = url.match(/^\/api\/properties\/([^/]+)\/staff\/enquiries/);
    if (!property) throw new Error("Unexpected endpoint");
    const slug = property[1];
    const success = (payload, status = 200) => ({
      ok: status >= 200 && status < 300, status,
      async json() { return payload; }
    });
    const requiredKey = slug === "demo-hotel" ? "staff-one" : "staff-two";
    if (options.headers["X-Staff-Key"] !== requiredKey) {
      return success({ detail: "Staff authentication required" }, 401);
    }
    if (options.method === "GET") {
      return success({ cases: database[slug].map((row) => ({ ...row })) });
    }
    const id = url.split("/").at(-2);
    const row = database[slug].find((entry) => entry.id === id);
    if (!row) return success({ detail: "Case not found" }, 404);
    if (url.endsWith("/claim") && row.status === "queued") {
      row.status = "claimed";
      return success({ status: "claimed" });
    }
    if (url.endsWith("/respond") && row.status === "claimed") {
      row.status = "responded";
      row.staff_reply = JSON.parse(options.body).message;
      return success({ status: "responded" });
    }
    return success({ detail: "Invalid transition" }, 409);
  };

  const source = fs.readFileSync(path.join(__dirname, "../staff.js"), "utf8");
  vm.runInNewContext(source, {
    document: {
      getElementById(name) {
        assert.ok(nodes[name], "Unexpected element ID: " + name);
        return nodes[name];
      },
      createElement(tag) { return new Node(tag); }
    },
    fetch,
    encodeURIComponent,
    crypto: webcrypto,
    Uint8Array
  }, { filename: "staff.js" });
  return { nodes, database, calls, linkedTickets };
}

test("loads property-scoped cases; shows actual counts; filters and searches without HTML injection", async () => {
  const { nodes, calls } = rig();
  await nodes.load.trigger("click");
  assert.equal(nodes["total-cases"].textContent, "2");
  assert.equal(nodes["queued-cases"].textContent, "1");
  assert.equal(nodes["claimed-cases"].textContent, "1");
  assert.equal(nodes["responded-cases"].textContent, "0");
  assert.equal(nodes["visible-count"].textContent, "2 of 2 loaded cases");
  assert.equal(descendants(nodes.cases, (n) => n.tagName === "H3")[0].textContent, "<img src=x>");
  assert.equal(descendants(nodes.cases, (n) => n.tagName === "IMG").length, 0);
  assert.equal(calls[0].cache, "no-store");

  nodes["filter-status"].value = "queued";
  await nodes["filter-status"].trigger("change");
  assert.equal(nodes["visible-count"].textContent, "1 of 2 loaded cases");
  nodes["filter-status"].value = "all";
  nodes["search-cases"].value = "reception";
  await nodes["search-cases"].trigger("input");
  assert.equal(nodes["visible-count"].textContent, "1 of 2 loaded cases");
  nodes["search-cases"].value = "no match";
  await nodes["search-cases"].trigger("input");
  assert.equal(descendants(nodes.cases, (n) => n.className === "case-empty").length, 1);
});

test("claim and reply remain real API actions; failure restores the button and prompts refresh", async () => {
  const { nodes, database, calls } = rig();
  await nodes.load.trigger("click");
  const claim = descendants(nodes.cases, (n) => n.tagName === "BUTTON" && n.textContent === "Claim this case")[0];
  assert.ok(claim, "Queued case must be claimable");
  await claim.trigger("click");
  assert.equal(database["demo-hotel"][0].status, "claimed");
  assert.equal(nodes["claimed-cases"].textContent, "2");

  const forms = descendants(nodes.cases, (n) => n.className === "case-reply-form");
  assert.equal(forms.length, 2);
  const firstTextarea = descendants(forms[0], (n) => n.tagName === "TEXTAREA")[0];
  firstTextarea.value = "Reception will contact the guest. This is not a confirmed booking.";
  await forms[0].trigger("submit");
  assert.equal(database["demo-hotel"][0].status, "responded");
  assert.equal(nodes["responded-cases"].textContent, "1");
  assert.ok(calls.some((c) => c.method === "POST" && c.url.endsWith("/respond")));
});

test("changing property or staff key immediately clears private cases and requires reauthorization", async () => {
  const { nodes } = rig();
  await nodes.load.trigger("click");
  nodes.p.value = "demo-hotel-two";
  await nodes.p.trigger("change");
  assert.equal(nodes["total-cases"].textContent, "—");
  assert.equal(nodes["visible-count"].textContent, "No cases loaded");
  assert.equal(descendants(nodes.cases, (n) => n.tagName === "H3").length, 0);

  await nodes.load.trigger("click");
  assert.match(nodes.message.textContent, /authentication required/i);
  assert.equal(nodes["total-cases"].textContent, "—");
  nodes.key.value = "staff-two";
  await nodes.key.trigger("input");
  await nodes.load.trigger("click");
  assert.equal(nodes["total-cases"].textContent, "1");
  assert.equal(descendants(nodes.cases, (n) => n.tagName === "H3")[0].textContent, "Other Property");
});

test("key visibility is opt-in and does not mutate the value", async () => {
  const { nodes } = rig();
  const original = nodes.key.value;
  await nodes["toggle-key"].trigger("click");
  assert.equal(nodes.key.type, "text");
  assert.equal(nodes["toggle-key"].attributes["aria-pressed"], "true");
  await nodes["toggle-key"].trigger("click");
  assert.equal(nodes.key.type, "password");
  assert.equal(nodes.key.value, original);
});

test("linked department handoff uses only a claimed case ID, and renders persisted ticket status", async () => {
  const { nodes, database, calls } = rig();
  await nodes.load.trigger("click");
  // Queued cases cannot create department work until claimed.
  assert.equal(descendants(nodes.cases.children[0], n => n.className === "case-ticket-form").length, 0);
  const claim = descendants(nodes.cases.children[0], n => n.tagName === "BUTTON" && n.textContent === "Claim this case")[0];
  await claim.trigger("click");

  const first = nodes.cases.children[0];
  const form = descendants(first, n => n.className === "case-ticket-form")[0];
  assert.ok(form, "Claimed case exposes a linked ticket form");
  const title = descendants(form, n => n.tagName === "INPUT")[0];
  const detail = descendants(form, n => n.tagName === "TEXTAREA")[0];
  title.value = "Inspect synthetic room";
  detail.value = "Check the synthetic room and record maintenance findings.";
  await form.trigger("submit");
  assert.equal(database["demo-hotel"][0].linked_ticket_id, "ticket-for-q-1");
  assert.equal(database["demo-hotel"][0].linked_ticket_status, "open");
  assert.equal(descendants(nodes.cases.children[0], n => n.className === "case-ticket-form").length, 0);
  const posted = calls.find(call => call.url.endsWith("/staff/tickets") && call.method === "POST");
  assert.ok(posted);
  const body = JSON.parse(posted.body);
  assert.equal(body.origin_case_id, "q-1");
  assert.equal(body.category, "reception");
  assert.ok(!posted.body.includes("<img src=x>"), "Guest names must not be copied into department payloads");
  assert.equal(posted.cache, "no-store");
});

test("lost department POST reply retains idempotency key across local retry", async () => {
  const { nodes, database, calls, linkedTickets } = rig({failTicketReplyOnce: true});
  await nodes.load.trigger("click");
  const form = descendants(nodes.cases.children[1], n => n.className === "case-ticket-form")[0];
  assert.ok(form);
  const title = descendants(form, n => n.tagName === "INPUT")[0];
  const detail = descendants(form, n => n.tagName === "TEXTAREA")[0];
  title.value = "Fix the staff device";
  detail.value = "A synthetic device requires local troubleshooting only.";
  await form.trigger("submit");
  assert.match(nodes.message.textContent, /not confirmed/);
  assert.equal(linkedTickets.size, 1);
  await form.trigger("submit");
  assert.equal(linkedTickets.size, 1);
  assert.equal(database["demo-hotel"][1].linked_ticket_id, "ticket-for-q-2");
  const callsToTickets = calls.filter(call => call.url.endsWith("/staff/tickets") && call.method === "POST");
  assert.equal(callsToTickets.length, 2);
  assert.equal(JSON.parse(callsToTickets[0].body).request_key, JSON.parse(callsToTickets[1].body).request_key);
});
