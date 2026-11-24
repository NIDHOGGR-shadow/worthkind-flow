"use strict";
const { test } = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

// No third-party libraries or real providers: exercises the actual UI script.
class Element {
  constructor(tag = "div") {
    this.tagName = tag.toUpperCase();
    this.children = [];
    this.attributes = {};
    this.handlers = {};
    this.textContent = "";
    this.className = "";
    this.value = "";
    this.disabled = false;
    this.hidden = false;
    this.type = "text";
  }
  addEventListener(name, handler) { (this.handlers[name] ||= []).push(handler); }
  async trigger(name) {
    return Promise.all((this.handlers[name] || []).map(handler => handler({ preventDefault() {} })));
  }
  setAttribute(name, value) { this.attributes[name] = String(value); }
  append(...items) { this.children.push(...items); }
  replaceChildren(...items) { this.children = items; }
}
function descendants(root, filter) {
  return root.children.flatMap(child => [
    ...(filter(child) ? [child] : []),
    ...descendants(child, filter)
  ]);
}
function snapshot(slug, n) {
  return {
    source: "property_scoped_local_sqlite",
    data_is_synthetic: true, production_ready: false,
    property: { slug, name: slug === "demo-hotel" ? "Demo Hotel A" : "Demo Hotel B" },
    as_of: "2026-11-19T16:00:00+00:00",
    cases: {
      total: n, by_status: { queued: n, claimed: 0, responded: 0 },
      recent: n ? [{id: "case-"+slug, kind: "<script>support</script>", status: "queued"}] : []
    },
    tickets: {
      total: n+1, unresolved: n+1, overdue: 0,
      recent: [{id: "ticket-"+slug, category: "maintenance", status: "open", priority: "high", due_at: "2030-01-01T00:00:00+00:00"}]
    },
    local_outbox: {pending_total: 3, pending_case_events: 1, pending_ticket_events: 2},
    unsupported: {occupancy: null, confirmed_bookings: null, hotel_payments: null, ai_conversations: null}
  };
}
function setup({delayed = false, wrongData = false} = {}) {
  const ids = [
    "overview-message", "overview-load", "overview-results", "overview-property",
    "overview-key", "overview-key-toggle", "overview-hotel-name", "overview-source",
    "overview-cases", "overview-tickets",
    "metric-case-total", "metric-case-queued", "metric-case-claimed", "metric-case-responded",
    "metric-ticket-total", "metric-ticket-unresolved", "metric-ticket-overdue", "metric-outbox-pending"
  ];
  const dom = Object.fromEntries(ids.map(id => [id, new Element()]));
  dom["overview-property"].value = "demo-hotel";
  dom["overview-key"].value = "key-a";
  dom["overview-key"].type = "password";
  dom["overview-results"].hidden = true;
  const calls = [];
  let releaseFirst;
  let firstRequest = true;
  const fetch = async (url, options) => {
    calls.push({url, options});
    if (delayed && firstRequest) {
      firstRequest = false;
      await new Promise(resolve => {releaseFirst = resolve;});
    }
    const slug = url.split("/")[3];
    const ok = options.headers["X-Staff-Key"] === (slug === "demo-hotel" ? "key-a" : "key-b");
    const result = wrongData ? {source:"fictional_dashboard", cases:{total:82}} : snapshot(slug, slug === "demo-hotel" ? 1 : 2);
    return {
      ok, status:ok?200:401,
      async json(){return ok?result:{detail:"Unauthorized"};}
    };
  };
  const source = fs.readFileSync(path.join(__dirname, "../overview.js"), "utf8");
  vm.runInNewContext(source, {
    document:{
      getElementById(id){
        assert.ok(dom[id], "Unexpected element: " + id);
        return dom[id];
      },
      createElement(tag){return new Element(tag);}
    },
    fetch, encodeURIComponent, Date, Number, String
  }, {filename:"overview.js"});
  return {dom, calls, release:()=>releaseFirst?.()};
}
test("renders actual property-scoped counts and no guest HTML execution", async () => {
  const {dom, calls} = setup();
  await dom["overview-load"].trigger("click");
  assert.equal(dom["overview-results"].hidden, false);
  assert.equal(dom["metric-case-total"].textContent, "1");
  assert.equal(dom["metric-ticket-total"].textContent, "2");
  assert.equal(dom["metric-outbox-pending"].textContent, "3");
  assert.equal(dom["overview-hotel-name"].textContent, "Demo Hotel A");
  assert.match(dom["overview-source"].textContent, /local property-scoped SQLite/);
  assert.equal(calls[0].options.cache,"no-store");
  assert.equal(calls[0].options.headers["X-Staff-Key"], "key-a");
  const text = descendants(dom["overview-cases"], el=>el.tagName==="STRONG");
  assert.equal(text[0].textContent, "Guest <script>support</script>");
  assert.equal(descendants(dom["overview-cases"], el=>el.tagName==="SCRIPT").length, 0);
  assert.equal(dom["overview-load"].disabled, false);
});
test("property switch immediately clears all private data; wrong staff key cannot unlock it", async () => {
  const {dom} = setup();
  await dom["overview-load"].trigger("click");
  dom["overview-property"].value = "demo-hotel-two";
  await dom["overview-property"].trigger("change");
  assert.equal(dom["overview-results"].hidden, true);
  assert.equal(dom["metric-case-total"].textContent, "—");
  assert.equal(dom["overview-cases"].children.length, 0);
  await dom["overview-load"].trigger("click");
  assert.equal(dom["overview-results"].hidden, true);
  assert.match(dom["overview-message"].textContent, /Unable to load/);
  dom["overview-key"].value = "key-b";
  await dom["overview-key"].trigger("input");
  await dom["overview-load"].trigger("click");
  assert.equal(dom["overview-results"].hidden, false);
  assert.equal(dom["metric-case-total"].textContent, "2");
  assert.equal(dom["overview-hotel-name"].textContent, "Demo Hotel B");
});
test("non-authoritative responses fail closed even with a successful HTTP status", async () => {
  const {dom} = setup({wrongData:true});
  await dom["overview-load"].trigger("click");
  assert.equal(dom["overview-results"].hidden, true);
  assert.equal(dom["metric-case-total"].textContent, "—");
});
test("late earlier-hotel HTTP response cannot overwrite the selected property", async () => {
  const {dom, release} = setup({delayed:true});
  const oldLoad = dom["overview-load"].trigger("click");
  // The first fetch is delayed. Reauthorization for the second hotel wins.
  dom["overview-property"].value="demo-hotel-two";
  await dom["overview-property"].trigger("change");
  dom["overview-key"].value="key-b";
  await dom["overview-key"].trigger("input");
  await dom["overview-load"].trigger("click");
  release();
  await oldLoad;
  assert.equal(dom["overview-hotel-name"].textContent,"Demo Hotel B");
  assert.equal(dom["metric-case-total"].textContent,"2");
});
test("key show/hide is deliberate and does not change its contents", async () => {
  const {dom} = setup();
  await dom["overview-key-toggle"].trigger("click");
  assert.equal(dom["overview-key"].type,"text");
  assert.equal(dom["overview-key-toggle"].attributes["aria-pressed"],"true");
  await dom["overview-key-toggle"].trigger("click");
  assert.equal(dom["overview-key"].type,"password");
  assert.equal(dom["overview-key"].value,"key-a");
});
