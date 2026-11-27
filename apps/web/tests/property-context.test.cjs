"use strict";
const {test}=require("node:test");
const assert=require("node:assert/strict");
const {capabilityMessage,createPropertyController}=require("../property-context.js");
const element=(value="")=>({value,textContent:"",dataset:{},disabled:false,addEventListener(){}});
const response=data=>({ok:true,json:async()=>data});
function rig(fetcher){
  const select=element("hotel-a"),name=element(),status=element(),load=element();
  const controller=createPropertyController({select,name,status,load,fetcher});
  return {select,name,status,load,...controller};
}
test("booking capability never exposes an unsupported checkout",()=>{
  assert.match(capabilityMessage({name:"A"},{mode:"enquiry_only"}),/not confirmed/);
  assert.match(capabilityMessage({name:"A"},{mode:"live",payments:true}),/supports enquiries only/);
  assert.throws(()=>capabilityMessage({},{}));
});
test("reads both authoritative endpoints without caching",async()=>{
  const calls=[];
  const x=rig(async(url,options)=>{calls.push([url,options.cache]);return response(url.endsWith("/booking-capabilities")?{mode:"enquiry_only"}:{slug:"hotel-a",name:"Hotel A"});});
  await x.refresh();
  assert.deepEqual(calls,[["/api/properties/hotel-a","no-store"],["/api/properties/hotel-a/booking-capabilities","no-store"]]);
  assert.equal(x.name.textContent,"Hotel A");
  assert.equal(x.status.dataset.state,"ready");
  assert.equal(x.load.disabled,false);
});
test("offline and mismatched property data fail closed",async()=>{
  const offline=rig(async()=>{throw Error("offline")});
  await offline.refresh();
  assert.equal(offline.status.dataset.state,"error");
  assert.equal(offline.load.disabled,false);
  const wrong=rig(async url=>response(url.endsWith("/booking-capabilities")?{mode:"enquiry_only"}:{slug:"other",name:"Other property"}));
  await wrong.refresh();
  assert.equal(wrong.status.dataset.state,"error");
  assert.notEqual(wrong.name.textContent,"Other property");
});
test("stale responses cannot overwrite the newly selected property",async()=>{
  let release;const gate=new Promise(r=>release=r);
  const x=rig(async url=>{const old=url.includes("hotel-a");if(old)await gate;
    return response(url.endsWith("/booking-capabilities")?{mode:"enquiry_only"}:{slug:old?"hotel-a":"hotel-b",name:old?"Hotel A":"Hotel B"});
  });
  const first=x.refresh();x.select.value="hotel-b";await x.refresh();release();await first;
  assert.equal(x.name.textContent,"Hotel B");
  assert.equal(x.status.dataset.state,"ready");
});
