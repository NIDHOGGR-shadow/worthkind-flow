"use strict";
const {test}=require("node:test");
const assert=require("node:assert/strict");
const {managementApi}=require("../management-core.js");
const id="12345678-1234-1234-1234-123456789abc",other="22345678-1234-1234-1234-123456789abc";
const receipt={slug:"hotel-a",case_id:id,token:"a".repeat(64)};
const identity={token:()=>"synthetic.staff.token"};
const ok=data=>({ok:true,json:async()=>data});
test("CMS draft and publication are property-scoped and explicit",async()=>{
 const calls=[];const api=managementApi(async(url,options)=>{calls.push([url,options]);return ok({id,state:url.endsWith("/decision")?"published":"draft"});},identity);
 const body={key:"hotel-information",title:"Hotel information",body:"Approved test content",source_reference:"Approved fixture"};
 await api.draft("hotel-a",body);await api.contentDecision("hotel-a",id,"publish");
 assert.deepEqual(JSON.parse(calls[0][1].body),body);assert.deepEqual(JSON.parse(calls[1][1].body),{action:"publish"});
 assert.ok(calls.every(([url,o])=>url.startsWith("/api/v1/properties/hotel-a/staff/")&&o.headers.Authorization==="Bearer synthetic.staff.token"&&o.cache==="no-store"));
 await assert.rejects(api.draft("../hotel",body));await assert.rejects(api.contentDecision("hotel-a",id,"force"));assert.equal(calls.length,2);
});
test("stock quantities use decimal strings, receipts require positive movement, retry proof is preserved",async()=>{
 const calls=[];const api=managementApi(async(url,options)=>{calls.push([url,options]);return ok({id,balance:"12.500",duplicate:false});},identity);
 const body={item_id:id,order_id:other,quantity_delta:"2.500",reason:"Received stock",request_key:"fixture-12345"};
 await api.movement("hotel-a",body);await api.movement("hotel-a",body);assert.deepEqual(calls[0][1].body,calls[1][1].body);
 await assert.rejects(api.movement("hotel-a",{...body,quantity_delta:"-1"}));await assert.rejects(api.movement("hotel-a",{...body,quantity_delta:"1.2345"}));assert.equal(calls.length,2);
});
test("supplier approval and purchase authorization verify exact result",async()=>{
 const api=managementApi(async(url)=>ok({id,state:"approved"}),identity);
 await api.supplierState("hotel-a",id,"approved");await api.purchaseDecision("hotel-a",id,"approve");
 await assert.rejects(api.supplierState("hotel-a",other,"approved"));await assert.rejects(api.purchaseDecision("hotel-a",id,"cancel"));
});
test("public vacancy reads never send staff or guest proof, applications require consent",async()=>{
 const calls=[];const api=managementApi(async(url,options)=>{calls.push([url,options]);return ok(url.endsWith("/vacancies")?{vacancies:[{id,title:"Reception",description:"Published fixture vacancy",deadline:"2026-12-01"}]}:{id,state:"submitted"});},identity);
 await api.vacancies("hotel-a");assert.equal(calls[0][1].headers.Authorization,undefined);assert.equal(calls[0][1].headers["X-Receipt-Token"],undefined);
 const body={vacancy_id:id,statement:"Synthetic statement",qualifications:"",consent:true};await api.apply(receipt,body);assert.equal(calls[1][1].headers["X-Receipt-Token"],receipt.token);assert.equal(calls[1][1].headers.Authorization,undefined);
 await assert.rejects(api.apply(receipt,{...body,consent:false}));assert.equal(calls.length,2);
});
test("preferences use verified receipt and monotonic server revision",async()=>{
 const api=managementApi(async(url,options)=>ok(options.method==="GET"?{preferences:null,revision:0}:{revision:1}),identity);
 assert.equal((await api.preferences(receipt)).revision,0);const body={language:"English",accessibility_requests:"",service_preferences:"",revision:0};
 assert.equal((await api.savePreferences(receipt,body)).revision,1);
 await assert.rejects(api.savePreferences(receipt,{...body,revision:1}));await assert.rejects(api.preferences({...receipt,token:"short"}));
});
test("guest feedback and staff resolution have different authorization and verified states",async()=>{
 const calls=[];const api=managementApi(async(url,options)=>{calls.push(options);return ok({id,state:url.endsWith("/review")?"resolved":"new"});},identity);
 await api.feedback(receipt,{rating:4,comment:"Synthetic feedback"});await api.feedbackReview("hotel-a",id,"resolve");
 assert.equal(calls[0].headers["X-Receipt-Token"],receipt.token);assert.equal(calls[1].headers.Authorization,"Bearer synthetic.staff.token");
 await assert.rejects(api.feedback(receipt,{rating:6,comment:""}));await assert.rejects(api.feedbackReview("hotel-a",other,"resolve"));
});
test("denials and uncertain outcomes are surfaced rather than retried automatically",async()=>{
 let calls=0;const api=managementApi(async()=>{calls++;return {ok:false,status:503};},identity);
 await assert.rejects(api.procurement("hotel-a"));assert.equal(calls,1);
});

test("purchase batches reject duplicate items and verify atomic decision",async()=>{
 const calls=[];const api=managementApi(async(u,o)=>{calls.push([u,o]);return ok(u.endsWith("/decision")?{id,action:"approve",line_count:2}:{id})},identity);
 const body={supplier_id:id,currency:"NGN",request_key:"fixture-batch",lines:[{item_id:id,quantity:"1.500",unit_price_minor:200},{item_id:other,quantity:"2",unit_price_minor:300}]};
 await api.batch("hotel-a",body);await api.batchDecision("hotel-a",id,"approve");await assert.rejects(api.batch("hotel-a",{...body,lines:[body.lines[0],body.lines[0]]}));assert.equal(calls.length,2);
});
test("consent policy version comes from published content, never a default",async()=>{
 const calls=[];const api=managementApi(async(u,o)=>{calls.push([u,o]);return ok(o.method==="GET"?{content:[{key:"privacy-policy",version:3,content:{title:"Published policy",body:"Synthetic approved policy text"}}]}:{id,purpose:"marketing",granted:false})},identity);
 const policy=await api.publishedPrivacyPolicy("hotel-a");assert.equal(policy.version,"privacy-policy:3");await api.consent(receipt,{purpose:"marketing",granted:false,policy_version:policy.version});assert.equal(calls[0][1].headers.Authorization,undefined);assert.equal(calls[1][1].headers["X-Receipt-Token"],receipt.token);
 assert.equal(await managementApi(async()=>ok({content:[]})).publishedPrivacyPolicy("hotel-a"),null);
});
