"use strict";
const {test}=require("node:test");
const assert=require("node:assert/strict");
const {nativeBookingApi}=require("../native-booking-core.js");
const id="12345678-1234-1234-1234-123456789abc",rate="22345678-1234-1234-1234-123456789abc";
const a={slug:"hotel-a",case_id:id,token:"a".repeat(64)},identity={token:()=>"synthetic.staff.token"};
const b={id,rate_id:rate,room_type_id:id,intent_id:id,state:"held",arrival:"2026-12-01",departure:"2026-12-03",room_count:1,currency:"NGN",total_minor:10000000,revision:1,policy_reference:"Hotel approved terms version 1"};
const ok=data=>({ok:true,json:async()=>data});
test("native availability is read-only, distinct from held inventory",async()=>{
 const d={source:"native_inventory",inventory_held:false,room_types:[{room_type_id:id,name:"Deluxe",max_guests:2,rooms_available:1,rates:[{id:rate,code:"STD",currency:"NGN",nightly_total_minor:5000000,policy_reference:b.policy_reference}]}]};
 const calls=[];const api=nativeBookingApi(async(u,o)=>{calls.push([u,o]);return ok(d)},identity);
 const rows=await api.availability("hotel-a",b.arrival,b.departure);assert.equal(api.total(rows[0].rates[0],b.arrival,b.departure,1),b.total_minor);
 assert.equal(calls[0][1].headers.Authorization,undefined);assert.equal(calls[0][1].method,"GET");
 await assert.rejects(api.availability("hotel-a",b.arrival,b.arrival));
 await assert.rejects(nativeBookingApi(async()=>ok({...d,inventory_held:true})).availability("hotel-a",b.arrival,b.departure));
});
test("staff hold retry retains exact proof and scoped identifiers",async()=>{
 const calls=[];const api=nativeBookingApi(async(u,o)=>{calls.push([u,o]);return ok(b)},identity);
 const payload={intent_id:id,room_type_id:id,rate_id:rate,request_key:"fixture-hold-key"};
 await api.hold("hotel-a",payload);await api.hold("hotel-a",payload);assert.equal(calls[0][1].body,calls[1][1].body);
 assert.equal(calls[0][1].headers.Authorization,"Bearer synthetic.staff.token");
 await assert.rejects(api.hold("hotel-a",{...payload,rate_id:id}));
});
test("confirmation requires terms, exact total and receipt, never confirms payment",async()=>{
 const calls=[];const reply={booking:{...b,state:"confirmed",revision:2},source:"native_inventory",booking_confirmed:true,payment_confirmed:false,payment_method:"pay_at_property"};
 const api=nativeBookingApi(async(u,o)=>{calls.push([u,o]);return ok(reply)},identity);
 await assert.rejects(api.confirm(a,b,false));assert.equal(calls.length,0);
 assert.equal((await api.confirm(a,b,true)).state,"confirmed");
 assert.deepEqual(JSON.parse(calls[0][1].body),{expected_total_minor:b.total_minor,payment_method:"pay_at_property",accept_terms:true});
 assert.equal(calls[0][1].headers["X-Receipt-Token"],a.token);assert.equal(calls[0][1].headers.Authorization,undefined);
 await assert.rejects(nativeBookingApi(async()=>ok({...reply,payment_confirmed:true})).confirm(a,b,true));
});
test("booking changes verify revision, currency, dates and recomputed server total",async()=>{
 const current={...b,state:"confirmed",revision:2};const quote={id:rate,arrival:"2026-12-04",departure:"2026-12-07",currency:"NGN",nightly_total_minor:5000000,policy_reference:b.policy_reference};
 const next={...current,arrival:quote.arrival,departure:quote.departure,total_minor:15000000,revision:3};
 const calls=[];const api=nativeBookingApi(async(u,o)=>{calls.push([u,o]);return ok({booking:next,source:"native_inventory",payment_method:"pay_at_property"})});
 await api.change(a,current,quote,true);assert.equal(JSON.parse(calls[0][1].body).expected_total_minor,15000000);assert.equal(JSON.parse(calls[0][1].body).revision,2);
 await assert.rejects(api.change(a,current,{...quote,currency:"USD"},true));
 await assert.rejects(nativeBookingApi(async()=>ok({booking:{...next,revision:2},source:"native_inventory",payment_method:"pay_at_property"})).change(a,current,quote,true));
});
test("cancellation is authorized and server-verified",async()=>{
 const api=nativeBookingApi(async()=>ok({...b,state:"cancelled",revision:2}),identity);assert.equal((await api.cancel("hotel-a",b,"Guest requested cancellation")).state,"cancelled");
 await assert.rejects(api.cancel("hotel-a",b,"short"));await assert.rejects(api.cancel("hotel-a",{...b,state:"expired"},"Guest requested cancellation"));
});
