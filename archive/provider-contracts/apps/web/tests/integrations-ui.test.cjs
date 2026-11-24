"use strict";
const {test} = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const path = require("node:path");

class Node {
  constructor(tag="div") {
    this.tagName=tag.toUpperCase(); this.children=[];this.handlers={};
    this.value="";this.textContent="";this.type="";this.disabled=false;
    this.hidden=false;this.attributes={};this.className="";
  }
  addEventListener(k,fn){(this.handlers[k] ||= []).push(fn);}
  setAttribute(k,v){this.attributes[k]=String(v);}
  replaceChildren(...nodes){this.children=nodes;}
  append(...nodes){this.children.push(...nodes);}
  async trigger(k){for(const fn of this.handlers[k]||[])await fn({preventDefault(){}});}
}
const ids=[
  "property","staff-key","show-key","load-readiness","connection-message",
  "readiness-content","readiness-empty","readiness-property","readiness-source",
  "authority","providers"
];
function snapshot(slug="demo-hotel") {
  return {
    property:slug,source:"disabled_development_adapters",production_connected:false,
    live_bookings:false,live_payments:false,live_messages:false,live_ai:false,
    services:["pms_availability","pms_reservation","hotel_payment","guest_messaging","optional_ai"]
      .map(service=>({service,mode:"disabled",configured:false,authoritative:false,
        description:"<img src=x onerror=alert(1)> No authorized provider connected."}))
  };
}
function ok(body,status=200){
  return {ok: status>=200&&status<300,status,async json(){return body;}};
}
function rig(provider=async()=>ok(snapshot())) {
  const nodes=Object.fromEntries(ids.map(id=>[id,new Node()]));
  nodes.property.value="demo-hotel";
  nodes["staff-key"].value="dev-key-one";
  nodes["staff-key"].type="password";
  nodes["readiness-content"].hidden=true;
  const calls=[];
  const fetch=async (url,options)=>{
    calls.push({url,options});
    return provider(url,options);
  };
  vm.runInNewContext(
    fs.readFileSync(path.join(__dirname,"../integrations.js"),"utf8"),
    {
      document:{
        getElementById(id){assert.ok(nodes[id],"Unknown ID "+id);return nodes[id];},
        createElement(tag){return new Node(tag);}
      },fetch,encodeURIComponent,Error
    },{filename:"integrations.js"}
  );
  return {nodes,calls};
}

test("loads five provider-disabled statuses from property-scoped API, not synthetic success",async()=>{
  const {nodes,calls}=rig();
  await nodes["load-readiness"].trigger("click");
  assert.equal(nodes["readiness-content"].hidden,false);
  assert.equal(nodes.providers.children.length,5);
  assert.equal(nodes["readiness-property"].textContent,"demo-hotel");
  assert.match(nodes.authority.textContent,/No authorized PMS/);
  assert.equal(calls.length,1);
  assert.equal(calls[0].options.cache,"no-store");
  assert.equal(calls[0].options.headers["X-Staff-Key"],"dev-key-one");
  const third=nodes.providers.children[2];
  assert.equal(third.tagName,"ARTICLE");
  assert.ok(third.children.some(n=>n.textContent.includes("<img src=x")));
  assert.equal(third.children.filter(n=>n.tagName==="IMG").length,0);
});

test("wrong property and forged configured/payment truth fail closed",async()=>{
  const forged=snapshot("demo-hotel");
  forged.services[2].configured=true;
  const {nodes}=rig(async()=>ok(forged));
  await nodes["load-readiness"].trigger("click");
  assert.equal(nodes["readiness-content"].hidden,true);
  assert.equal(nodes.providers.children.length,0);
  assert.match(nodes["connection-message"].textContent,/unverified provenance|Unexpected adapter authority/);

  const next=rig(async()=>ok(snapshot("demo-hotel-two")));
  await next.nodes["load-readiness"].trigger("click");
  assert.equal(next.nodes["readiness-content"].hidden,true);
});

test("property change erases previous loaded details and drops stale in-flight response",async()=>{
  let release;
  const pending=new Promise(resolve=>{release=resolve;});
  const {nodes}=rig(async()=>pending);
  const original=nodes["load-readiness"].trigger("click");
  nodes.property.value="demo-hotel-two";
  await nodes.property.trigger("change");
  assert.equal(nodes["staff-key"].value,"");
  assert.equal(nodes["readiness-content"].hidden,true);
  assert.equal(nodes["readiness-property"].textContent,"—");
  release(ok(snapshot("demo-hotel")));
  await original;
  assert.equal(nodes["readiness-content"].hidden,true);
  assert.equal(nodes.providers.children.length,0);
});

test("empty key avoids requests, auth denial displays safe error and toggles key explicitly",async()=>{
  const {nodes,calls}=rig(async()=>ok({detail:"Staff authentication required"},401));
  nodes["staff-key"].value="";
  await nodes["load-readiness"].trigger("click");
  assert.equal(calls.length,0);
  assert.equal(nodes["readiness-content"].hidden,true);

  await nodes["show-key"].trigger("click");
  assert.equal(nodes["staff-key"].type,"text");
  assert.equal(nodes["show-key"].attributes["aria-pressed"],"true");
  await nodes["show-key"].trigger("click");
  assert.equal(nodes["staff-key"].type,"password");
  assert.equal(nodes["show-key"].attributes["aria-pressed"],"false");

  nodes["staff-key"].value="wrong-key";
  await nodes["staff-key"].trigger("input");
  await nodes["load-readiness"].trigger("click");
  assert.equal(calls.length,1);
  assert.equal(nodes["readiness-content"].hidden,true);
  assert.match(nodes["connection-message"].textContent,/Access denied/);
});
