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

test("Q2 roster and shift contracts enforce date ranges and membership identifiers",async()=>{
 const calls=[],start="2026-11-25T08:00:00.000Z",end="2026-11-25T16:00:00.000Z";
 const api=staffApi(async(url,options)=>{calls.push({url,options});return ok(url.includes("/schedule?")?{members:[{membership_id:id}],shifts:[{id,membership_id:id,state:"scheduled"}]}:url.endsWith("/cancel")?{id,state:"cancelled"}:url.includes("/profiles/")?{membership_id:id}:{id,state:"scheduled"})},identity);
 await api.schedule("hotel-a",start,end);
 await api.saveProfile("hotel-a",id,{display_name:"Test staff",job_title:"Reception",employee_reference:"EMP-01"});
 await api.createShift("hotel-a",id,start,end);
 await api.cancelShift("hotel-a",id);
 assert.match(calls[0].url,/\/schedule\?start=/);
 assert.deepEqual(JSON.parse(calls[2].options.body),{membership_id:id,starts_at:start,ends_at:end});
 await assert.rejects(api.createShift("hotel-a",id,end,start));
 await assert.rejects(api.schedule("hotel-a",start,"2027-11-25T16:00:00.000Z"));
 await assert.rejects(api.createShift("hotel-a","invalid",start,end));
 assert.equal(calls.length,4);
});
test("Q2 room condition requires revision and confirms matching server update",async()=>{
 const calls=[];const api=staffApi(async(url,options)=>{calls.push({url,options});return ok(options.method==="GET"?{rooms:[{id,label:"312",room_type_id:id,operational_state:"dirty",revision:2}]}:{id,operational_state:"inspecting",revision:3})},identity);
 await api.rooms("hotel-a");await api.roomState("hotel-a",id,"inspecting",2);
 assert.deepEqual(JSON.parse(calls[1].options.body),{state:"inspecting",revision:2});
 await assert.rejects(api.roomState("hotel-a",id,"available",2));await assert.rejects(api.roomState("hotel-a",id,"clean",0));
 assert.equal(calls.length,2);
 await assert.rejects(staffApi(async()=>ok({id,operational_state:"clean",revision:2}),identity).roomState("hotel-a",id,"clean",2));
});
test("Q2 reception control includes reason and explicit transfer target",async()=>{
 const calls=[];const api=staffApi(async(url,options)=>{const b=JSON.parse(options.body);calls.push(b);return ok({case_id:id,state:{transfer:"claimed",escalate:"escalated",resolve:"resolved"}[b.action]});},identity);
 await api.caseControl("hotel-a",id,"transfer","Transfer to reception",id);
 await api.caseControl("hotel-a",id,"escalate","Manager review required");
 await api.caseControl("hotel-a",id,"resolve","Staff work completed");
 assert.deepEqual(calls[0],{action:"transfer",reason:"Transfer to reception",target_membership_id:id});
 assert.equal(calls[1].target_membership_id,null);
 await assert.rejects(api.caseControl("hotel-a",id,"transfer","Transfer to reception","invalid"));
 await assert.rejects(api.caseControl("hotel-a",id,"resolve","short"));
 assert.equal(calls.length,3);
});

test("ticket history is identity-bound and never accepts another record's response",async()=>{
 const calls=[];const history=[{actor:id,action:"note",note:"Synthetic history",created_at:"2026-11-25T10:00:00Z"}];
 const api=staffApi(async(url,options)=>{calls.push({url,options});return ok({id,status:"open",history})},identity);
 assert.deepEqual((await api.ticketDetail("hotel-a",id)).history,history);
 assert.equal(calls[0].url,"/api/v1/properties/hotel-a/staff/tickets/"+id);
 await assert.rejects(staffApi(async()=>ok({id:"aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",status:"open",history}),identity).ticketDetail("hotel-a",id));
 await assert.rejects(staffApi(async()=>ok({id,status:"open",history:[{action:"note",note:{},created_at:"2026-11-25"}]}),identity).ticketDetail("hotel-a",id));
});

test("staff hotel discovery uses authenticated global read, preserves invited state and rejects malformed cursor",async()=>{
 const calls=[];const property={id,slug:"hotel-a",display_name:"Hotel A",time_zone:"Africa/Lagos",role:"manager",membership_state:"invited"};
 const api=staffApi(async(url,o)=>{calls.push([url,o]);return ok({properties:[property],next_cursor:"hotel-a"});},identity);
 assert.equal((await api.properties()).properties[0].membership_state,"invited");
 assert.equal(calls[0][0],"/api/v1/staff/properties?limit=50");
 assert.equal(calls[0][1].headers.Authorization,"Bearer verified.test.token");
 await assert.rejects(api.properties("../other"));assert.equal(calls.length,1);
 await assert.rejects(staffApi(async()=>ok({properties:[{...property,membership_state:"revoked"}],next_cursor:null}),identity).properties());
});
test("staff resolution read rejects contradictory guest confirmation",async()=>{
 const snapshot={case_id:id,case_status:"resolved",resolution_id:id,guest_decision:"confirm",guest_confirmed:true,awaiting_guest_confirmation:false};
 assert.equal((await staffApi(async()=>ok(snapshot),identity).resolution("hotel-a",id)).guest_confirmed,true);
 await assert.rejects(staffApi(async()=>ok({...snapshot,awaiting_guest_confirmation:true}),identity).resolution("hotel-a",id));
});
