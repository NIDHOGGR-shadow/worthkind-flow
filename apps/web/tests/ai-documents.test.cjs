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

test("AI insights, usage and sources are scoped reads and acknowledgments are explicit",async()=>{
 const calls=[];const api=aiStudioApi(async(u,o)=>{calls.push([u,o]);return ok(u.endsWith("/sources")?{sources:[{id,title:"Hotel",content_key:"hotel",version:1,state:"published",ai_allowed:true}]}:u.endsWith("/usage")?{window_hours:24,used_units:3,channels:[{channel:"guest_chat",state:"answered",calls:2,units:3}]}:u.endsWith("/insights")?{ticket_counts:[{category:"maintenance",open_count:2,overdue_count:1}],alerts:[{id,ticket_id:id,category:"maintenance",priority:"high",due_at:"2026-11-26T00:00:00Z",state:"open"}]}:{acknowledged:true})},identity);
 assert.equal((await api.sources("hotel-a"))[0].ai_allowed,true);assert.equal((await api.usage("hotel-a")).used_units,3);assert.equal((await api.insights("hotel-a")).alerts.length,1);await api.acknowledge("hotel-a",id);assert.equal(calls[3][1].method,"POST");assert.ok(calls.every(([u,o])=>u.startsWith("/api/v1/properties/hotel-a/staff/ai/")&&o.headers.Authorization==="Bearer synthetic.staff.token"));
 await assert.rejects(aiStudioApi(async()=>ok({acknowledged:false}),identity).acknowledge("hotel-a",id));
});
test("ticket proposals require approval and only executed decisions may contain a ticket",async()=>{
 const b={request_key:"fixture-proposal",category:"maintenance",priority:"normal",subject:"Repair light",description:"Synthetic repair request"};
 const calls=[];const api=aiStudioApi(async(u,o)=>{calls.push([u,o]);return ok(u.endsWith("/decision")?{id,state:"executed",ticket_id:id}:{id,approval_required:true})},identity);
 await api.propose("hotel-a",b);await api.propose("hotel-a",b);assert.equal(calls[0][1].body,calls[1][1].body);assert.equal((await api.decide("hotel-a",id,true)).ticket_id,id);
 await assert.rejects(aiStudioApi(async()=>ok({id,state:"executed",ticket_id:null}),identity).decide("hotel-a",id,true));
 await assert.rejects(aiStudioApi(async()=>ok({id,approval_required:false}),identity).propose("hotel-a",b));
});
test("latest backend handoff requires no invented notification field",async()=>{
 const d={status:"handoff",reason:"voice_unavailable",answer:null,sources:[],human_handoff_required:true,action_executed:false};assert.equal((await aiStudioApi(async()=>ok(d)).chat("hotel-a","Hotel amenities?",true)).status,"handoff");
});
const {pcmVoiceWav,requestVoice}=require("../guest-voice.js");
test("voice encodes mono 16kHz PCM, requires explicit consent and never forwards identity",async()=>{
 const wav=pcmVoiceWav(new Float32Array(1600));const bytes=new DataView(await wav.arrayBuffer());assert.equal(wav.size,3244);assert.equal(bytes.getUint32(24,true),16000);assert.equal(bytes.getUint16(22,true),1);assert.equal(bytes.getUint16(34,true),16);
 const calls=[],reply={status:"handoff",reason:"model_unavailable",answer:null,sources:[],human_handoff_required:true,action_executed:false};const f=async(u,o)=>{calls.push([u,o]);return ok(reply);};
 await assert.rejects(requestVoice(f,"hotel-a",wav,false));assert.equal(calls.length,0);assert.equal((await requestVoice(f,"hotel-a",wav,true)).status,"handoff");assert.equal(calls[0][1].headers["X-Voice-Consent"],"true");assert.equal(calls[0][1].credentials,"omit");assert.throws(()=>pcmVoiceWav(new Float32Array(320001)));
 await assert.rejects(requestVoice(async()=>ok({...reply,action_executed:true}),"hotel-a",wav,true));
});
