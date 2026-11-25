"use strict";
const {test}=require("node:test");
const assert=require("node:assert/strict");
const {aiStudioApi}=require("../ai-studio-core.js");
const {privateDocumentApi}=require("../private-documents.js");
const id="12345678-1234-1234-1234-123456789abc", identity={token:()=>"synthetic.staff.token"};
const ok=data=>({ok:true,json:async()=>data});
test("AI owner policy requires a revision and confirms server values",async()=>{
 const calls=[],p={revision:1,guest_chat:false,staff_assist:true,autonomous_alerts:false,voice_enabled:false,max_calls_per_day:20};
 const api=aiStudioApi(async(u,o)=>{calls.push([u,o]);return ok({...p,revision:2});},identity);
 await api.save("hotel-a",p);assert.equal(calls[0][1].headers.Authorization,"Bearer synthetic.staff.token");
 await assert.rejects(api.save("hotel-a",{...p,revision:0}));assert.equal(calls.length,1);
 await assert.rejects(aiStudioApi(async()=>ok(p),identity).save("hotel-a",p));
});
test("AI source approvals bind the exact content version",async()=>{
 const api=aiStudioApi(async()=>ok({id,allowed:false}),identity);
 await api.source("hotel-a",id,false);await assert.rejects(api.source("hotel-a",id,true));
});
test("AI guest and staff assistance requires consent, approved sources and no executed action",async()=>{
 const calls=[],answer={status:"answered",answer:"Approved information",answer_type:"approved_content_excerpt",sources:[{id,key:"hotel",title:"Hotel",version:1}],action_executed:false};
 const api=aiStudioApi(async(u,o)=>{calls.push([u,o]);return ok(answer)},identity);
 await assert.rejects(api.chat("hotel-a","Hotel information?",false));assert.equal(calls.length,0);
 await api.chat("hotel-a","Hotel information?",true);await api.chat("hotel-a","Hotel information?",true,true);
 assert.equal(calls[0][1].headers.Authorization,undefined);assert.equal(calls[1][1].headers.Authorization,"Bearer synthetic.staff.token");
 for(const d of [{...answer,action_executed:true},{...answer,sources:[]},{...answer,answer_type:"free_text"}])await assert.rejects(aiStudioApi(async()=>ok(d)).chat("hotel-a","Hotel information?",true));
});
test("AI handoff is not a sent notification",async()=>{
 const handoff={status:"handoff",answer:null,sources:[],reason:"model_unavailable",human_contact_available_via_property:true,action_executed:false};
 assert.equal((await aiStudioApi(async()=>ok(handoff)).chat("hotel-a","Hotel information?",true)).status,"handoff");
});
test("private documents enforce size, identity and attachment-only responses",async()=>{
 const calls=[],blob=new Blob(["fixture"],{type:"application/octet-stream"});const api=privateDocumentApi(async(u,o)=>{calls.push([u,o]);return o.method==="POST"?ok({document_id:id,size:blob.size}):{ok:true,headers:new Headers({"content-type":"application/octet-stream","content-disposition":"attachment"}),blob:async()=>blob};},identity);
 assert.equal((await api.upload("hotel-a",blob)).document_id,id);assert.equal(calls[0][1].headers["Content-Type"],"application/octet-stream");
 assert.equal((await api.download("hotel-a",id)).size,blob.size);assert.equal(calls[1][1].headers.Authorization,"Bearer synthetic.staff.token");
 await assert.rejects(api.upload("hotel-a",new Blob([])));await assert.rejects(api.upload("hotel-a",{size:2000001}));await assert.rejects(api.download("hotel-a","../secret"));assert.equal(calls.length,2);
 await assert.rejects(privateDocumentApi(async()=>({ok:true,headers:new Headers({"content-type":"text/html","content-disposition":"inline"}),blob:async()=>blob}),identity).download("hotel-a",id));
});
