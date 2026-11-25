"use strict";
const {test}=require("node:test");
const assert=require("node:assert/strict");
const {guestApi,createGuestJourney}=require("../guest-v1-core.js");
const id="12345678-1234-1234-1234-123456789abc",token="a".repeat(64);
const fields={kind:"human",name:"Guest",contact:"guest@example.invalid",details:"Please contact reception."};
const body={...fields,request_key:"b".repeat(32),receipt_token:token};
const result={case_id:id,status:"queued",receipt_token:token};
const ok=data=>({ok:true,json:async()=>data});
const hex=n=>"a".repeat(n*2);
test("uses versioned same-origin API only and private proof headers",async()=>{
 const calls=[];const api=guestApi(async(url,options)=>{calls.push({url,options});return ok(result)});
 await api.submit("hotel-a",body);await api.status("hotel-a",id,token);
 assert.equal(calls[0].url,"/api/v1/properties/hotel-a/enquiries");
 assert.equal(calls[1].url,"/api/v1/properties/hotel-a/enquiries/"+id);
 assert.equal(calls[1].options.headers["X-Receipt-Token"],token);
 assert.ok(calls.every(c=>!c.url.includes(token)&&c.options.cache==="no-store"&&c.options.redirect==="error"));
});
test("rejects malformed hotel and proof before network",async()=>{
 let calls=0;const api=guestApi(async()=>{calls++;return ok(result)});
 await assert.rejects(api.status("../hotel",id,token));
 await assert.rejects(api.status("hotel-a","bad-id",token));
 await assert.rejects(api.status("hotel-a",id,"short"));
 assert.equal(calls,0);
});
test("rejects unverified receipt and unexpected state",async()=>{
 await assert.rejects(guestApi(async()=>ok({...result,receipt_token:"wrong"})).submit("hotel-a",body));
 await assert.rejects(guestApi(async()=>ok({...result,status:"confirmed"})).submit("hotel-a",body));
 await assert.rejects(guestApi(async()=>ok({...result,case_id:"aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"})).status("hotel-a",id,token));
});
test("backend outage or rate limit never fabricates a receipt or falls back",async()=>{
 for(const status of [404,409,422,429,503]){
   let calls=0;const api=guestApi(async()=>{calls++;return {ok:false,status}});
   await assert.rejects(api.submit("hotel-a",body));assert.equal(calls,1);
 }
});
test("lost response retries identical proof; prevents switching property",async()=>{
 let calls=[];const api={submit:async(slug,payload)=>{calls.push([slug,JSON.stringify(payload)]);if(calls.length===1)throw Error("lost response");return result}};
 const j=createGuestJourney(api,hex);
 await assert.rejects(j.submit("hotel-a",fields));assert.equal(j.pending,true);
 await assert.rejects(j.submit("hotel-b",fields));assert.equal(calls.length,1);
 await assert.rejects(j.submit("hotel-a",{...fields,name:"Different"}));assert.equal(calls.length,1);
 await j.submit("hotel-a",fields);assert.deepEqual(calls[0],calls[1]);assert.equal(j.pending,false);
 assert.equal(j.active.slug,"hotel-a");await assert.rejects(j.submit("hotel-a",fields));
});
test("concurrent submissions and resets are blocked",async()=>{
 let release;const gate=new Promise(r=>release=r);let calls=0;
 const j=createGuestJourney({submit:async()=>{calls++;await gate;return result}},hex);
 const first=j.submit("hotel-a",fields);await assert.rejects(j.submit("hotel-a",fields));
 assert.throws(()=>j.reset());await assert.rejects(j.recover("hotel-a",id,token));release();await first;assert.equal(calls,1);
});
test("private recovery refresh uses the original hotel; failed refresh preserves receipt",async()=>{
 let calls=[];const j=createGuestJourney({status:async(...args)=>{calls.push(args);if(calls.length===2)throw Error("offline");return {...result,status:"responded",staff_reply:"Recorded"};}},hex);
 await j.recover("hotel-a",id,token);await assert.rejects(j.refresh());assert.equal(j.active.token,token);
 assert.deepEqual(calls[0],calls[1]);j.reset();assert.equal(j.active,null);
});
