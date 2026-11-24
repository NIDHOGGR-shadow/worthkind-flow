"use strict";
const { test } = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const { webcrypto } = require("node:crypto");

class FakeNode {
  constructor(tag = "div") {
    this.tagName = tag.toUpperCase();
    this.textContent = "";
    this.value = "";
    this.type = "";
    this.className = "";
    this.hidden = false;
    this.disabled = false;
    this.children = [];
    this.handlers = {};
    this.attributes = {};
    this.resets = 0;
  }
  append(...children) { this.children.push(...children); }
  replaceChildren(...children) { this.children = children; }
  setAttribute(key, value) { this.attributes[key] = String(value); }
  addEventListener(type, fn) { (this.handlers[type] ||= []).push(fn); }
  reset() { this.resets++; }
  reportValidity() { return true; }
  focus() {}
  async trigger(type) {
    for (const handler of this.handlers[type] || []) {
      await handler({preventDefault() {}, currentTarget: this});
    }
  }
}

const ids = [
  "property", "staff-key", "show-key", "load-knowledge", "message",
  "knowledge-data", "knowledge-empty", "facts", "drafts", "revisions",
  "loaded-property", "draft-form", "review-reason", "preview-question",
  "preview-result", "draft-message", "question-key", "draft-answer",
  "source-reference", "draft-submit", "preview-button"
];
const stored = () => ({
  facts: [{
    question_key: "name", answer: "Demo Hotel A",
    approved: 1, version: 1, source: "synthetic_demo_fixture"
  }],
  drafts: [{
    id: "draft-one", question_key: "dining", answer: "<script>alert(1)</script> Synthetic restaurant details",
    source_reference: "Synthetic test source", status: "draft", base_version: 0
  }],
  history: [],
});

function rig(fetchHandler, state = stored()) {
  const nodes = Object.fromEntries(ids.map(id => [id, new FakeNode()]));
  nodes.property.value = "demo-hotel";
  nodes["staff-key"].value = "dev-key";
  nodes["staff-key"].type = "password";
  nodes["question-key"].value = "dining";
  nodes["draft-answer"].value = "Synthetic restaurant information needing a reviewer.";
  nodes["source-reference"].value = "Synthetic source notes";
  nodes["knowledge-data"].hidden = true;
  const calls = [];
  const fetch = async (url, opts) => {
    calls.push({url, opts});
    return fetchHandler(url, opts, state);
  };
  const source = fs.readFileSync(path.join(__dirname, "../knowledge.js"), "utf8");
  vm.runInNewContext(source, {
    document: {
      getElementById(id) {
        assert.ok(nodes[id], "Unexpected id " + id);
        return nodes[id];
      },
      createElement(tag) { return new FakeNode(tag); }
    },
    fetch, crypto: webcrypto, encodeURIComponent,
    Uint8Array, Set
  }, { filename: "knowledge.js" });
  return {nodes, calls, state};
}

function response(data, status = 200) {
  return {ok: status >= 200 && status < 300, status, async json() {return data;}};
}
function developmentApi(url, opts, state) {
  const property = url.match(/^\/api\/properties\/([^/]+)/)?.[1];
  if (!property) throw Error("Bad URL " + url);
  if (url.endsWith("/information")) {
    return response({status: "unknown", answer: null});
  }
  if (opts.headers["X-Staff-Key"] !== "dev-key") {
    return response({detail: "Staff authentication required"}, 401);
  }
  if (url.endsWith("/staff/knowledge") && opts.method === "GET") {
    return response({
      source: "local_sqlite_development", property,
      facts: state.facts, drafts: state.drafts,
      production_approval: false
    });
  }
  if (url.endsWith("/staff/knowledge/history") && opts.method === "GET") {
    return response({property, history: state.history, production_approval: false});
  }
  if (url.endsWith("/staff/knowledge/drafts") && opts.method === "POST") {
    const body = JSON.parse(opts.body);
    state.posted ||= [];
    state.posted.push(body);
    if (state.dropReplyOnce) {
      state.dropReplyOnce = false;
      throw Error("Synthetic connection lost");
    }
    state.drafts.push({
      ...body, id: "submitted-draft", base_version: 0, status: "draft"
    });
    return response({draft_id: "submitted-draft", status: "draft"}, 201);
  }
  if (url.endsWith("/approve") && opts.method === "POST") {
    state.drafts = state.drafts.map(d => ({...d, status: "approved"}));
    state.facts.push({question_key: "dining", answer: "Locally reviewed dining info",
      version: 1, approved: 1, source: "local_development_review:synthetic"});
    state.history.push({question_key: "dining", version: 1, approved: 1,
      answer: "Locally reviewed dining info", actor: "dev-staff:demo-hotel"});
    return response({status: "approved", version: 1});
  }
  return response({detail: "Unexpected action"}, 404);
}

function descendants(root, predicate) {
  const result = [];
  for (const child of root.children) {
    if (predicate(child)) result.push(child);
    result.push(...descendants(child, predicate));
  }
  return result;
}

test("staff knowledge view renders property-scoped synthetic facts with safe text", async () => {
  const {nodes, calls} = rig(developmentApi);
  await nodes["load-knowledge"].trigger("click");
  assert.equal(nodes["knowledge-data"].hidden, false);
  assert.equal(nodes["loaded-property"].textContent, "demo-hotel");
  assert.equal(nodes.facts.children.length, 1);
  assert.equal(nodes.drafts.children.length, 1);
  const visible = nodes.drafts.children[0];
  assert.ok(descendants(visible, n => n.tagName === "P")
    .some(n => n.textContent.includes("<script>")));
  assert.equal(descendants(visible, n => n.tagName === "SCRIPT").length, 0);
  assert.equal(calls.length, 2);
  assert.ok(calls.every(c => c.opts.cache === "no-store"));
});

test("hotel or development key changes erase facts, draft cards and reviewer input", async () => {
  const {nodes} = rig(developmentApi);
  await nodes["load-knowledge"].trigger("click");
  nodes.property.value = "demo-hotel-two";
  await nodes.property.trigger("change");
  assert.equal(nodes["staff-key"].value, "");
  assert.equal(nodes.facts.children.length, 0);
  assert.equal(nodes.drafts.children.length, 0);
  assert.equal(nodes["knowledge-data"].hidden, true);
  assert.equal(nodes["loaded-property"].textContent, "—");

  nodes["staff-key"].value = "different-key";
  await nodes["staff-key"].trigger("input");
  await nodes["load-knowledge"].trigger("click");
  assert.equal(nodes["knowledge-data"].hidden, true);
  assert.match(nodes.message.textContent, /authentication required/i);
});

test("review approval is a real POST followed by new property-scoped read", async () => {
  const state = stored();
  const {nodes, calls} = rig(developmentApi, state);
  await nodes["load-knowledge"].trigger("click");
  const approve = descendants(nodes.drafts, n => n.tagName === "BUTTON" && /Approve/.test(n.textContent))[0];
  assert.ok(approve, "Pending draft must offer approval");
  await approve.trigger("click");
  assert.equal(state.facts.some(f => f.question_key === "dining"), true);
  assert.equal(nodes.facts.children.length, 2);
  assert.equal(nodes.revisions.children.length, 1);
  assert.ok(calls.some(c => c.url.endsWith("/approve") && c.opts.method === "POST"));
  assert.equal(nodes.drafts.children.length, 1); // empty-state, no pending draft cards
  assert.match(nodes.message.textContent, /approved/i);
});

test("new draft retry preserves idempotency key after lost server reply", async () => {
  const state = stored();
  state.dropReplyOnce = true;
  const {nodes, calls} = rig(developmentApi, state);
  await nodes["draft-form"].trigger("submit");
  assert.match(nodes["draft-message"].textContent, /not confirmed/);
  await nodes["draft-form"].trigger("submit");
  assert.equal(state.posted.length, 2);
  assert.equal(state.posted[0].request_key, state.posted[1].request_key);
  assert.equal(nodes["draft-submit"].disabled, false);
  assert.equal(calls.filter(c => c.url.endsWith("/drafts") && c.opts.method === "POST").length, 2);
});

test("public FAQ preview refuses to invent an unpublished answer", async () => {
  const {nodes} = rig(developmentApi);
  nodes["preview-question"].value = "Is a restaurant menu available?";
  await nodes["preview-button"].trigger("click");
  assert.match(nodes["preview-result"].textContent, /No approved answer/);
  assert.equal(nodes["preview-button"].disabled, false);
});
