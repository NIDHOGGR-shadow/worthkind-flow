"use strict";
const {test}=require("node:test");
const assert=require("node:assert/strict");
const {providerEvidenceApi}=require("../provider-evidence-core.js");
const id="12345678-1234-1234-1234-123456789abc",identity={token:()=>"synthetic.staff.token"};
const ok=data=>({ok:true,json:async()=>data});
test("POS evidence is order-bound and cannot confirm settlement",async()=>{
 const calls=[],d={source:"loyverse",payment_settled_by_this_action:false,evidence:{id,order_id:id,receipt_number:"POS-1",matched:true,amount_minor:500,currency:"NGN"}};
 const api=providerEvidenceApi(async(u,o)=>{calls.push([u,o]);return ok(d)},identity);
 assert.equal((await api.reconcilePos("hotel-a",id,"POS-1")).matched,true);assert.equal(calls[0][1].headers.Authorization,"Bearer synthetic.staff.token");await assert.rejects(providerEvidenceApi(async()=>ok({...d,payment_settled_by_this_action:true}),identity).reconcilePos("hotel-a",id,"POS-1"));
});
test("PMS evidence cannot independently prove guest identity",async()=>{
 const d={source:"cloudbeds",guest_identity_link_independently_verified:false,evidence:{id,external_reservation_id:"PMS-1",provider_state:"confirmed",retrieved_at:"2026-11-25T22:00:00Z"}};
 const api=providerEvidenceApi(async()=>ok(d),identity);await api.syncPms("hotel-a","PMS-1",id);await assert.rejects(api.syncPms("hotel-a","PMS-2",id));
});
test("settlement comparison keeps mode and does not claim a bank deposit",async()=>{
 const d={settlement_id:1,page:1,mode:"test",bank_deposit_independently_verified:false,transactions:[{reference:"fixture",amount_minor:500,currency:"NGN",comparison:"matched_verified_payment"}]};
 const api=providerEvidenceApi(async()=>ok(d),identity);assert.equal((await api.settlementTransactions("hotel-a",1,1)).mode,"test");
 await assert.rejects(providerEvidenceApi(async()=>ok({...d,bank_deposit_independently_verified:true}),identity).settlementTransactions("hotel-a",1,1));await assert.rejects(api.settlementTransactions("hotel-a",2,1));
});

test("PMS write requires guest authorization and binds the command key",async()=>{
 const b={intent_id:id,request_key:"fixture-command",first_name:"Test",last_name:"Guest",country:"NG",postal_code:"100001",email:"guest@example.invalid",guest_authorized:true};
 const calls=[];const api=providerEvidenceApi(async(u,o)=>{calls.push([u,o]);return ok({command:{id,operation:"create",request_key:b.request_key,state:"verified"},payment_confirmed:false})},identity);
 await assert.rejects(api.createReservation("hotel-a",{...b,guest_authorized:false}));assert.equal(calls.length,0);await api.createReservation("hotel-a",b);assert.equal(calls.length,1);await assert.rejects(api.createReservation("hotel-a",{...b,request_key:"different-key"}));
});
test("PMS rate jobs remain separate from OTA delivery",async()=>{
 const b={request_key:"fixture-rate",rate_id:"RATE-1",start:"2026-12-01",end:"2026-12-03",nightly_minor:50000};
 const api=providerEvidenceApi(async()=>ok({command:{id,operation:"rate_update",request_key:b.request_key,state:"accepted"},ota_delivery_verified:false}),identity);
 assert.equal((await api.updateRate("hotel-a",b)).state,"accepted");
 await assert.rejects(providerEvidenceApi(async()=>ok({command:{id,operation:"rate_update",request_key:b.request_key,state:"verified"},ota_delivery_verified:true}),identity).verifyRate("hotel-a",id));
});
