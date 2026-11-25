"use strict";
function aiStudioApi(fetcher,session){
 const uuid=/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
 const valid=x=>{if(!x)throw Error("Invalid AI request or unexpected server response.");};
 const flags=["guest_chat","staff_assist","autonomous_alerts","voice_enabled"];
 const policy=d=>{valid(d&&Number.isSafeInteger(d.revision)&&d.revision>=1&&flags.every(k=>typeof d[k]==="boolean")&&Number.isInteger(d.max_calls_per_day)&&d.max_calls_per_day>=1&&d.max_calls_per_day<=1000);return d;};
 async function call(s,p,m="GET",b,staff=true){valid(typeof s==="string"&&s.length<=100&&/^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(s));const headers={Accept:"application/json"};if(staff)headers.Authorization="Bearer "+session.token();if(b!==undefined)headers["Content-Type"]="application/json";let r;try{r=await fetcher("/api/v1/properties/"+encodeURIComponent(s)+(staff?"/staff":"")+p,{method:m,headers,...(b===undefined?{}:{body:JSON.stringify(b)}),cache:"no-store",credentials:"same-origin",redirect:"error"});}catch{throw Error("AI service unavailable. Contact hotel staff directly.");}if(!r.ok)throw Object.assign(Error(({401:"Session rejected.",403:"AI access denied.",409:"Policy or usage conflict. Reload.",429:"Usage limit reached.",503:"AI service unavailable."})[r.status]||"AI service did not confirm the request."),{status:r.status});return r.json();}
 return {
  async policy(s){return policy(await call(s,"/ai/policy"));},
  async save(s,b){policy(b);const body={revision:b.revision,max_calls_per_day:b.max_calls_per_day};for(const k of flags)body[k]=b[k];const d=policy(await call(s,"/ai/policy","PUT",body));valid(d.revision>b.revision&&flags.every(k=>d[k]===b[k])&&d.max_calls_per_day===b.max_calls_per_day);return d;},
  async source(s,i,allowed){valid(typeof i==="string"&&uuid.test(i)&&typeof allowed==="boolean");const d=await call(s,"/ai/sources/"+i,"PUT",{allowed});valid(d.id===i&&d.allowed===allowed);return d;},
  async chat(s,q,consent,staff=false){valid(typeof q==="string"&&q.trim().length>=3&&q.length<=800&&consent===true);const d=await call(s,"/ai/chat","POST",{question:q.trim(),consent_to_model_processing:true},staff);valid(d.action_executed===false&&Array.isArray(d.sources));if(d.status==="handoff"){valid(d.answer===null&&d.sources.length===0&&typeof d.reason==="string"&&d.human_contact_available_via_property===true);return d;}valid(d.status==="answered"&&d.answer_type==="approved_content_excerpt"&&typeof d.answer==="string"&&d.answer.length>0&&d.answer.length<=30000&&d.sources.length>0&&d.sources.every(r=>uuid.test(r.id)&&typeof r.title==="string"&&typeof r.key==="string"&&Number.isSafeInteger(r.version)&&r.version>=1));return d;}
 };
}
function renderApprovedAi(root,result){
 root.replaceChildren();const node=(t,v)=>{const n=document.createElement(t);n.textContent=v;return n;};
 if(result.status==="handoff"){root.append(node("h3","Contact hotel staff"),node("p","No approved answer was returned. Use the human enquiry or reception channel. This did not send a message or transfer a call."));return;}
 const answer=node("p",result.answer);answer.className="approved-ai-excerpt";root.append(node("h3","Approved hotel information"),answer,node("h4","Sources"));for(const s of result.sources)root.append(node("p",s.title+" · version "+s.version+" · "+s.key));root.append(node("p","Information only. No booking, payment, staff action or notification was executed."));
}
if(typeof module!=="undefined"&&module.exports)module.exports={aiStudioApi};
