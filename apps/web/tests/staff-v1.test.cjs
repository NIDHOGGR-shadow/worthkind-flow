"use strict";
const {test}=require("node:test");
const assert=require("node:assert/strict");
const {staffConfig,staffSession,staffApi,staffContext}=require("../staff-v1-core.js");
const cfg={enabled:true,provider:"supabase",url:"https://abcdefghijklmnopqrst.supabase.co",publishableKey:"sb_publishable_test_only"};
const id="12345678-1234-1234-1234-123456789abc";
const good={access_token:"test.token.value",expires_in:60,user:{role:"authenticated",is_anonymous:false,email_confirmed_at:"2026-11-25"}};
const ok=data=>({ok:true,json:async()=>data});
const identity={token:()=>"verified.test.token"};
test("configuration fails closed for arbitrary origin, disabled state, and privileged keys",()=>{
 assert.throws(()=>staffConfig({...cfg,enabled:false}));
 assert.throws(()=>staffConfig({...cfg,url:"https://example.com"}));
 assert.throws(()=>staffConfig({...cfg,publishableKey:"sb_secret_test"}));
 assert.equal(staffConfig(cfg).url,cfg.url);
});
test("verified session expires, refuses unconfirmed identities and clears locally on logout",async()=>{
 let now=1000;const calls=[];const s=staffSession(async(url,options)=>{calls.push({url,options});return ok(good)},cfg,()=>now);
 await s.signIn("staff@example.invalid","synthetic-password");
 assert.equal(s.token(),good.access_token);
 assert.equal(calls[0].url,cfg.url+"/auth/v1/token?grant_type=password");
 assert.equal(calls[0].options.redirect,"error");
 assert.equal(await s.signOut(),true);assert.equal(s.signedIn,false);
 assert.match(calls[1].url,/logout\?scope=local$/);
 await s.signIn("staff@example.invalid","synthetic-password");now+=60001;assert.throws(()=>s.token());
 const anon=staffSession(async()=>ok({...good,user:{...good.user,is_anonymous:true}}),cfg);
 await assert.rejects(anon.signIn("test","test"));assert.equal(anon.signedIn,false);
 const unconfirmed=staffSession(async()=>ok({...good,user:{...good.user,email_confirmed_at:null}}),cfg);
 await assert.rejects(unconfirmed.signIn("test","test"));
});
test("staff queue and claim use bearer authorization and property-scoped versioned paths",async()=>{
 const calls=[];const api=staffApi(async(url,options)=>{calls.push({url,options});return ok(options.method==="GET"?{property:"hotel-a",staff_role:"reception",cases:[{id,status:"queued"}]}:{property:"hotel-a",case_id:id,status:"claimed"})},identity);
 await api.cases("hotel-a");await api.caseAction("hotel-a",id,"claim");
 assert.equal(calls[0].url,"/api/v1/properties/hotel-a/staff/cases");
 assert.equal(calls[1].url,"/api/v1/properties/hotel-a/staff/cases/"+id+"/claim");
 assert.ok(calls.every(c=>c.options.headers.Authorization==="Bearer verified.test.token"&&c.options.cache==="no-store"&&c.options.redirect==="error"));
 await assert.rejects(api.cases("../hotel-b"));assert.equal(calls.length,2);
});
test("cross-property, unauthorized, and invalid transition responses fail closed",async()=>{
 await assert.rejects(staffApi(async()=>ok({property:"hotel-b",staff_role:"manager",cases:[]}),identity).cases("hotel-a"));
 for(const status of [401,403,404,409,503])await assert.rejects(staffApi(async()=>({ok:false,status}),identity).cases("hotel-a"));
 await assert.rejects(staffApi(async()=>ok({property:"hotel-a",case_id:id,status:"queued"}),identity).caseAction("hotel-a",id,"claim"));
});
test("ticket creation and transition use backend request contract",async()=>{
 const calls=[];const api=staffApi(async(url,options)=>{calls.push({url,options});return ok(url.endsWith("/transition")?{ticket_id:id,status:"in_progress"}:{ticket_id:id,status:"open"})},identity);
 const body={request_key:"test-key-123",category:"maintenance",priority:"high",subject:"Fault",description:"Test work order"};
 await api.createTicket("hotel-a",body);await api.ticketAction("hotel-a",id,"start","Working on issue");
 assert.deepEqual(JSON.parse(calls[0].options.body),body);
 assert.deepEqual(JSON.parse(calls[1].options.body),{action:"start",note:"Working on issue"});
});
test("membership and settings commands transmit only expected fields",async()=>{
 const calls=[];const api=staffApi(async(url,options)=>{calls.push({url,options});return ok(url.endsWith("/settings")?{guest_enquiries_enabled:false,ai_enabled:false,revision:3}:{membership_id:id,state:"invited",role:"reception"})},identity);
 await api.membership("hotel-a","invite","provider-subject","reception");
 await api.updateSettings("hotel-a",2,false);
 assert.deepEqual(JSON.parse(calls[0].options.body),{provider_subject:"provider-subject",role:"reception"});
 assert.deepEqual(JSON.parse(calls[1].options.body),{revision:2,guest_enquiries_enabled:false});
 await assert.rejects(api.membership("hotel-a","invite","provider-subject","admin"));
 await assert.rejects(api.updateSettings("hotel-a",0,true));assert.equal(calls.length,2);
});
test("stale response from prior property cannot update workspace",async()=>{
 const ctx=staffContext();ctx.select("hotel-a");let release;const gate=new Promise(r=>release=r);
 const previous=ctx.run(async slug=>{await gate;return slug});
 await assert.rejects(ctx.run(async()=>null));ctx.select("hotel-b");
 assert.equal(await ctx.run(async slug=>slug),"hotel-b");release();await assert.rejects(previous);
 assert.equal(ctx.slug,"hotel-b");assert.equal(ctx.busy,false);
});
