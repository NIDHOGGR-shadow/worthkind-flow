"use strict";
function managementApi(fetcher,session){
 const uuid=/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
 const error=(message,status=0)=>Object.assign(new Error(message),{status});
 const requireValue=(v)=>{if(!v)throw error("Invalid data or unexpected server response. Check the current records.");};
 const id=v=>{requireValue(typeof v==="string"&&uuid.test(v));return v;};
 const str=(v,min,max)=>typeof v==="string"&&v.length>=min&&v.length<=max;
 const key=v=>str(v,8,100)&&/^[A-Za-z0-9_-]+$/.test(v);
 const decimal=(v,positive=false)=>typeof v==="string"&&/^-?\d{1,15}(?:\.\d{1,3})?$/.test(v)&&Number.isFinite(Number(v))&&(!positive||Number(v)>0);
 const list=(d,k,check)=>{requireValue(Array.isArray(d?.[k])&&d[k].every(check));return d[k];};
 const record=r=>r&&typeof r.id==="string"&&uuid.test(r.id);
 const stateRecord=r=>record(r)&&typeof r.state==="string";
 const result=(d,expected,state)=>{requireValue(record(d)&&(!expected||d.id===expected)&&(!state||d.state===state));return d;};
 const date=v=>str(v,10,10)&&/^\d{4}-\d{2}-\d{2}$/.test(v)&&Number.isFinite(Date.parse(v))&&new Date(v).toISOString().slice(0,10)===v;
 async function call(slug,path,method="GET",body,access="staff",token){
   requireValue(str(slug,1,100)&&/^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(slug));
   const headers={Accept:"application/json"};
   if(access==="staff")headers.Authorization="Bearer "+session.token();
   if(access==="guest"){requireValue(str(token,32,128)&&/^[A-Za-z0-9_-]+$/.test(token));headers["X-Receipt-Token"]=token;}
   if(body!==undefined)headers["Content-Type"]="application/json";
   let r;try{r=await fetcher("/api/v1/properties/"+encodeURIComponent(slug)+path,{method,headers,...(body===undefined?{}:{body:JSON.stringify(body)}),credentials:"same-origin",cache:"no-store",redirect:"error"});}catch{throw error("Connection interrupted; action outcome is unknown. Check records before retrying.");}
   if(!r.ok)throw error(({401:"Session rejected. Sign in again.",403:"Access denied.",404:"Record unavailable.",409:"Conflict. Refresh before retrying.",422:"Check submitted details.",429:"Rate limit reached.",503:"Service unavailable or action outcome unknown."})[r.status]||"Service did not confirm the operation.",r.status);
   try{return await r.json();}catch{throw error("Unreadable service response.");}
 }
 const staff=(s,p,m,b)=>call(s,"/staff"+p,m,b);
 const guest=(a,p,m,b)=>call(a.slug,"/guest/cases/"+id(a.case_id)+p,m,b,"guest",a.token);
 const decision=async(s,path,i,action,states)=>{requireValue(Object.hasOwn(states,action));return result(await staff(s,path+"/"+id(i)+"/decision","POST",{action}),i,states[action]);};
 return {
  async content(s){return list(await staff(s,"/content"),"content",r=>stateRecord(r)&&str(r.key,2,80)&&Number.isInteger(r.version)&&r.content&&str(r.content.title,2,160)&&str(r.content.body,8,3500));},
  async draft(s,b){requireValue(str(b.key,2,80)&&/^[a-z0-9][a-z0-9_-]+$/.test(b.key)&&str(b.title,2,160)&&str(b.body,8,3500)&&str(b.source_reference,8,240));return result(await staff(s,"/content","POST",b),null,"draft");},
  contentDecision:(s,i,a)=>decision(s,"/content",i,a,{publish:"published",reject:"rejected",withdraw:"withdrawn"}),
  async procurement(s){const d=await staff(s,"/procurement");return {items:list(d,"items",r=>record(r)&&typeof r.name==="string"&&Number.isFinite(Number(r.balance))&&Number.isFinite(Number(r.reorder_level))),suppliers:list(d,"suppliers",stateRecord),orders:list(d,"orders",stateRecord)};},
  async item(s,b){requireValue(str(b.sku,2,60)&&/^[A-Za-z0-9_-]+$/.test(b.sku)&&str(b.name,2,160)&&str(b.unit,1,24)&&decimal(b.reorder_level)&&Number(b.reorder_level)>=0);return result(await staff(s,"/stock/items","POST",b));},
  async supplier(s,b){requireValue(str(b.name,2,160)&&str(b.external_reference,2,100));return result(await staff(s,"/suppliers","POST",b),null,"pending");},
  async supplierState(s,i,state){requireValue(["approved","suspended"].includes(state));return result(await staff(s,"/suppliers/"+id(i)+"/state","PUT",{state}),i,state);},
  async purchase(s,b){id(b.supplier_id);id(b.item_id);requireValue(decimal(b.quantity,true)&&Number.isSafeInteger(b.unit_price_minor)&&b.unit_price_minor>=0&&b.unit_price_minor<=1000000000000&&/^[A-Z]{3}$/.test(b.currency)&&key(b.request_key));return result(await staff(s,"/purchase-orders","POST",b));},
  purchaseDecision:(s,i,a)=>decision(s,"/purchase-orders",i,a,{approve:"approved",cancel:"cancelled"}),
  async movement(s,b){id(b.item_id);if(b.order_id)id(b.order_id);requireValue(decimal(b.quantity_delta)&&Number(b.quantity_delta)!==0&&(!b.order_id||Number(b.quantity_delta)>0)&&str(b.reason,4,240)&&key(b.request_key));const d=result(await staff(s,"/stock/movements","POST",b));requireValue(decimal(d.balance)&&typeof d.duplicate==="boolean");return d;},
  async batches(s){return list(await staff(s,"/purchase-batches"),"batches",r=>record(r)&&uuid.test(r.supplier_id)&&/^[A-Z]{3}$/.test(r.currency)&&Array.isArray(r.lines)&&r.lines.length>=1&&r.lines.every(l=>uuid.test(l.order_id)&&uuid.test(l.item_id)&&typeof l.state==="string"&&Number.isFinite(Number(l.quantity))&&Number.isSafeInteger(l.unit_price_minor)));},
  async batch(s,b){id(b.supplier_id);requireValue(key(b.request_key)&&/^[A-Z]{3}$/.test(b.currency)&&Array.isArray(b.lines)&&b.lines.length>=1&&b.lines.length<=50&&new Set(b.lines.map(l=>l.item_id)).size===b.lines.length&&b.lines.every(l=>uuid.test(l.item_id)&&decimal(l.quantity,true)&&Number.isSafeInteger(l.unit_price_minor)&&l.unit_price_minor>=0&&l.unit_price_minor<=1000000000000));return result(await staff(s,"/purchase-batches","POST",b));},
  async batchDecision(s,i,a){requireValue(["approve","cancel"].includes(a));const d=result(await staff(s,"/purchase-batches/"+id(i)+"/decision","POST",{action:a}),i);requireValue(d.action===a&&Number.isInteger(d.line_count)&&d.line_count>=1&&d.line_count<=50);return d;},
  async vacancies(s){return list(await call(s,"/vacancies","GET",undefined,"public"),"vacancies",r=>record(r)&&str(r.title,2,160)&&str(r.description,8,4000)&&date(r.deadline));},
  async vacancy(s,b){requireValue(str(b.title,2,160)&&str(b.description,8,4000)&&date(b.deadline));return result(await staff(s,"/vacancies","POST",b),null,"draft");},
  vacancyDecision:(s,i,a)=>decision(s,"/vacancies",i,a,{publish:"published",close:"closed"}),
  async apply(a,b){id(b.vacancy_id);requireValue(str(b.statement,8,4000)&&str(b.qualifications,0,3000)&&b.consent===true);return result(await guest(a,"/applications","POST",b),null,"submitted");},
  async applications(s){return list(await staff(s,"/applications"),"applications",r=>stateRecord(r)&&uuid.test(r.vacancy_id)&&uuid.test(r.case_id)&&str(r.statement,8,4000));},
  applicationDecision:(s,i,a)=>decision(s,"/applications",i,a,{review:"reviewing",shortlist:"shortlisted",reject:"rejected",select:"selected"}),
  async preferences(a){const d=await guest(a,"/preferences");requireValue(Number.isInteger(d?.revision)&&d.revision>=0&&(d.preferences===null||(d.preferences&&str(d.preferences.language,0,40)&&str(d.preferences.accessibility_requests,0,1000)&&str(d.preferences.service_preferences,0,1000))));return d;},
  async savePreferences(a,b){requireValue(Number.isInteger(b.revision)&&b.revision>=0&&str(b.language,0,40)&&str(b.accessibility_requests,0,1000)&&str(b.service_preferences,0,1000));const d=await guest(a,"/preferences","PUT",b);requireValue(Number.isInteger(d?.revision)&&d.revision>b.revision);return d;},
  async consent(a,b){requireValue(["service_followup","marketing"].includes(b.purpose)&&typeof b.granted==="boolean"&&str(b.policy_version,1,80));const d=result(await guest(a,"/consent","POST",b));requireValue(d.purpose===b.purpose&&d.granted===b.granted);return d;},
  async feedback(a,b){requireValue(Number.isInteger(b.rating)&&b.rating>=1&&b.rating<=5&&str(b.comment,0,2000));return result(await guest(a,"/feedback","POST",b),null,"new");},
  async feedbackQueue(s){return list(await staff(s,"/feedback"),"feedback",r=>stateRecord(r)&&uuid.test(r.case_id)&&Number.isInteger(r.rating)&&r.rating>=1&&r.rating<=5);},
  async feedbackReview(s,i,a){requireValue(["review","resolve"].includes(a));return result(await staff(s,"/feedback/"+id(i)+"/review","POST",{action:a}),i,a==="review"?"reviewed":"resolved");}
 };
}
if(typeof module!=="undefined"&&module.exports)module.exports={managementApi};
