"use strict";
const { test } = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const { webcrypto } = require("node:crypto");

// Isolated fake DOM. Covers interactions; does NOT replace real browser a11y QA.
class Node {
  constructor() {
    this.value = "";
    this.type = "text";
    this.textContent = "";
    this.hidden = false;
    this.disabled = false;
    this.attributes = {};
    this.handlers = {};
    this.scrolled = 0;
    this.resets = 0;
  }
  addEventListener(name, fn) { (this.handlers[name] ||= []).push(fn); }
  setAttribute(key, value) { this.attributes[key] = String(value); }
  scrollIntoView() { this.scrolled++; }
  reset() { this.resets++; }
  async trigger(name) {
    const pending = [];
    for (const fn of this.handlers[name] || []) pending.push(fn({ preventDefault() {} }));
    await Promise.all(pending);
  }
}

function harness(shared = { cases: new Map(), calls: [], failNext: false }) {
  const ids = [
    "human-bypass", "check-intent", "question", "hotel", "category", "name", "contact", "details",
    "enquiry-form", "submission-result", "track", "receipt", "case-status", "refresh",
    "recover-form", "recover-hotel", "recover-case-id", "recover-token", "recover-result",
    "recover-submit", "recover-toggle", "copy-receipt", "new-enquiry", "new-request",
    "routing-result"
  ];
  const nodes = Object.fromEntries(ids.map(id => [id, new Node()]));
  nodes["enquiry-submit"] = new Node();
  nodes.hotel.value = "demo-hotel";
  nodes.category.value = "booking";
  nodes.name.value = "Synthetic Guest";
  nodes.contact.value = "guest@example.invalid";
  nodes.details.value = "Please call me about a room next Friday.";
  nodes["recover-hotel"].value = "demo-hotel";
  nodes["recover-token"].type = "password";
  nodes.track.hidden = true;

  const fetch = async (url, options = {}) => {
    shared.calls.push({ url, options });
    const response = (status, payload) => ({
      ok: status >= 200 && status < 300, status,
      async json() { return payload; }
    });

    if (options.method === "POST" && url.endsWith("/enquiries")) {
      const slug = url.split("/")[3];
      const data = JSON.parse(options.body);
      const requestId = slug + ":" + data.request_key;
      let row = shared.cases.get(requestId);
      if (!row) {
        row = {
          slug, id: "11111111-2222-4333-8444-" +
            String(shared.cases.size + 1).padStart(12, "0"),
          token: data.receipt_token, status: "queued", staff_reply: null
        };
        shared.cases.set(requestId, row);
      }
      if (shared.failNext) {
        shared.failNext = false;
        // HTTP response is lost AFTER local persistence, not a dropped request.
        throw new Error("Synthetic network failure");
      }
      return response(201, {
        case_id: row.id, receipt_token: data.receipt_token, status: row.status,
        duplicate: shared.cases.size > 0, message: "Local enquiry queued; not a reservation."
      });
    }

    const match = url.match(/^\/api\/properties\/([^/]+)\/enquiries\/([^/?]+)$/);
    if (options.method === "GET" && match) {
      const [, slug, id] = match;
      const token = options.headers["X-Receipt-Token"];
      const found = [...shared.cases.values()].find(
        row => row.slug === slug && row.id === id && row.token === token
      );
      if (!found) return response(404, { detail: "Enquiry not found" });
      return response(200, {
        case_id: found.id, status: found.status, staff_reply: found.staff_reply,
        kind: "booking"
      });
    }
    throw new Error("Unexpected fetch " + options.method + " " + url);
  };

  const source = fs.readFileSync(path.join(__dirname, "../app.js"), "utf8");
  vm.runInNewContext(source, {
    document: {
      querySelector(query) {
        if (query === "#enquiry-form button[type=submit]") return nodes["enquiry-submit"];
        assert.ok(query.startsWith("#"), "Unexpected selector " + query);
        const id = query.slice(1);
        assert.ok(nodes[id], "Missing fake element " + query);
        return nodes[id];
      },
      querySelectorAll(query) {
        assert.equal(query, "[data-kind]");
        return [];
      }
    },
    fetch,
    crypto: webcrypto,
    navigator: {
      clipboard: {
        async writeText(text) { shared.clipboardText = text; }
      }
    },
    Uint8Array,
    encodeURIComponent,
    Error,
    Set
  }, { filename: "app.js" });
  return { nodes, shared };
}

test("local guest can recover a private receipt after full reload without browser storage", async () => {
  const shared = { cases: new Map(), calls: [], failNext: false };
  const first = harness(shared);
  await first.nodes["enquiry-form"].trigger("submit");
  assert.equal(shared.cases.size, 1);
  assert.equal(first.nodes.track.hidden, false);
  const saved = [...shared.cases.values()][0];
  assert.ok(first.nodes.receipt.textContent.includes(saved.token));

  // Completely new JS context; user supplies original secrets themselves.
  const second = harness(shared);
  second.nodes["recover-case-id"].value = saved.id;
  second.nodes["recover-token"].value = saved.token;
  await second.nodes["recover-form"].trigger("submit");
  assert.equal(second.nodes.track.hidden, false);
  assert.ok(second.nodes.receipt.textContent.includes(saved.id));
  assert.equal(second.nodes["recover-token"].value, "");
  assert.match(second.nodes["recover-result"].textContent, /verified locally/i);
  const read = shared.calls.find(c => c.options.method === "GET");
  assert.equal(read.options.cache, "no-store");
  assert.equal(read.options.headers["X-Receipt-Token"], saved.token);

  await second.nodes["copy-receipt"].trigger("click");
  assert.ok(shared.clipboardText.includes(saved.id));
  assert.ok(shared.clipboardText.includes(saved.token));
});

test("wrong hotel or private token cannot reveal any case", async () => {
  const shared = { cases: new Map(), calls: [], failNext: false };
  const prior = harness(shared);
  await prior.nodes["enquiry-form"].trigger("submit");
  const row = [...shared.cases.values()][0];
  const next = harness(shared);
  next.nodes["recover-case-id"].value = row.id;
  next.nodes["recover-token"].value = "Z".repeat(40);
  await next.nodes["recover-form"].trigger("submit");
  assert.equal(next.nodes.track.hidden, true);
  assert.match(next.nodes["recover-result"].textContent, /Could not verify/);
  assert.ok(!next.nodes["recover-result"].textContent.includes(row.id));

  next.nodes["recover-hotel"].value = "demo-hotel-two";
  next.nodes["recover-token"].value = row.token;
  await next.nodes["recover-form"].trigger("submit");
  assert.equal(next.nodes.track.hidden, true);
});

test("lost response permits exact retry with same secret/idempotency key", async () => {
  const shared = { cases: new Map(), calls: [], failNext: true };
  const { nodes } = harness(shared);
  await nodes["enquiry-form"].trigger("submit");
  assert.equal(shared.cases.size, 1);
  assert.match(nodes["submission-result"].textContent, /Submission not confirmed/);
  assert.equal(nodes["enquiry-submit"].disabled, false);
  await nodes["enquiry-form"].trigger("submit");
  assert.equal(shared.cases.size, 1);
  assert.equal(nodes.track.hidden, false);
  const submits = shared.calls.filter(c => c.options.method === "POST");
  assert.equal(submits.length, 2);
  assert.equal(JSON.parse(submits[0].options.body).request_key, JSON.parse(submits[1].options.body).request_key);
  assert.equal(JSON.parse(submits[0].options.body).receipt_token, JSON.parse(submits[1].options.body).receipt_token);
});

test("new enquiry creates a distinct request; changing property rekeys retries", async () => {
  const shared = { cases: new Map(), calls: [], failNext: false };
  const { nodes } = harness(shared);
  await nodes["enquiry-form"].trigger("submit");
  const original = JSON.parse(shared.calls[0].options.body);
  await nodes["new-enquiry"].trigger("click");
  assert.equal(nodes.track.hidden, true);
  assert.equal(nodes["enquiry-form"].resets, 1);
  await nodes["enquiry-form"].trigger("submit");
  const newRequest = JSON.parse(shared.calls[1].options.body);
  assert.notEqual(original.request_key, newRequest.request_key);
  assert.equal(shared.cases.size, 2);

  nodes.hotel.value = "demo-hotel-two";
  await nodes["enquiry-form"].trigger("submit");
  const newHotel = JSON.parse(shared.calls[2].options.body);
  assert.notEqual(newRequest.request_key, newHotel.request_key);
  assert.equal(shared.cases.size, 3);
});

test("receipt show/hide is explicit and has accessible pressed state", async () => {
  const { nodes } = harness();
  await nodes["recover-toggle"].trigger("click");
  assert.equal(nodes["recover-token"].type, "text");
  assert.equal(nodes["recover-toggle"].attributes["aria-pressed"], "true");
  await nodes["recover-toggle"].trigger("click");
  assert.equal(nodes["recover-token"].type, "password");
  assert.equal(nodes["recover-toggle"].attributes["aria-pressed"], "false");
});
