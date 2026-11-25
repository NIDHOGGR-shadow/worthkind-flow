"use strict";
function providerEvidenceApi(fetcher,session){
 const uuid=/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
 const valid=x=>{if(!x)throw Error("Invalid provider record or unexpected response.");};
 const identifier=x=>{valid(typeof x==="string"&&/^[A-Za-z0-9_-]{1,100}$/.test(x));return x;};
 const id=x=>{valid(typeof x==="string"&&uuid.test(x));return x;};
 const list=(d,k,check)=>{valid(Array.isArray(d?.[k])&&d[k].every(check));return d[k];};
 const amount=x=>Number.isSafeInteger(x)&&x>=0;
 const curr=x=>typeof x==="string"&&/^[A-Z]{3}$/.test(x);
 async function call(s,p,m="GET",body){
  valid(typeof s==="string"&&s.length<=100&&/^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(s));
  const headers={Accept:"application/json",Authorization:"Bearer "+session.token()};if(body!==undefined)headers["Content-Type"]="application/json";
  let r;try{r=await fetcher("/api/v1/properties/"+encodeURIComponent(s)+"/staff"+p,{method:m,headers,...(body===undefined?{}:{body:JSON.stringify(body)}),cache:"no-store",credentials:"same-origin",redirect:"error"});}catch{throw Error("Connection interrupted; outcome unknown. Check provider records before repeating.");}
  if(!r.ok)throw Object.assign(Error(({401:"Session rejected.",403:"Access denied.",404:"Provider record unavailable.",409:"Provider evidence conflict. Investigate before repeating.",422:"Check submitted details.",429:"Rate limited.",503:"Provider service unavailable or outcome unknown."})[r.status]||"Provider request not confirmed."),{status:r.status});
  try{return await r.json();}catch{throw Error("Unreadable provider response.");}
 }
 const pos=r=>r&&uuid.test(r.id)&&uuid.test(r.order_id)&&typeof r.receipt_number==="string"&&typeof r.matched==="boolean"&&amount(r.amount_minor)&&curr(r.currency);
 const pms=r=>r&&uuid.test(r.id)&&typeof r.external_reservation_id==="string"&&typeof r.provider_state==="string"&&typeof r.retrieved_at==="string";
 const page=p=>{valid(Number.isInteger(p)&&p>=1&&p<=10000);return p;};
 const settlementId=v=>{valid(Number.isSafeInteger(v)&&v>0);return v;};
 return {
  async pos(s){const d=await call(s,"/pos/reconciliation");valid(d.source==="loyverse");return list(d,"receipts",pos);},
  async reconcilePos(s,order,receipt){const d=await call(s,"/pos/orders/"+id(order)+"/reconcile","POST",{receipt_number:identifier(receipt)});valid(d.source==="loyverse"&&d.payment_settled_by_this_action===false&&pos(d.evidence)&&d.evidence.order_id===order&&d.evidence.receipt_number===receipt);return d.evidence;},
  async pms(s){const d=await call(s,"/pms/reservation-evidence");valid(d.source==="last_verified_cloudbeds_readback");return list(d,"reservations",pms);},
  async syncPms(s,reference,intent){if(intent)id(intent);const d=await call(s,"/pms/reservation-evidence","POST",{reservation_id:identifier(reference),intent_id:intent||null});valid(d.source==="cloudbeds"&&d.guest_identity_link_independently_verified===false&&pms(d.evidence)&&d.evidence.external_reservation_id===reference);return d.evidence;},
  async commands(s){return list(await call(s,"/pms/commands"),"commands",r=>r&&uuid.test(r.id)&&typeof r.operation==="string"&&typeof r.state==="string");},
  async settlements(s,p){const d=await call(s,"/finance/settlements?page="+page(p));valid(d.source==="paystack"&&d.page===p&&d.bank_deposit_independently_verified===false);return list(d,"settlements",r=>Number.isSafeInteger(r.id)&&r.id>0&&["test","live"].includes(r.mode)&&curr(r.currency)&&["total_amount","effective_amount","total_fees","total_processed"].every(k=>Number.isSafeInteger(r[k])));},
  async settlementTransactions(s,i,p){const d=await call(s,"/finance/settlements/"+settlementId(i)+"/transactions?page="+page(p));valid(d.settlement_id===i&&d.page===p&&["test","live"].includes(d.mode)&&d.bank_deposit_independently_verified===false);return {mode:d.mode,rows:list(d,"transactions",r=>typeof r.reference==="string"&&amount(r.amount_minor)&&curr(r.currency)&&typeof r.comparison==="string")};}
 };
}
if(typeof module!=="undefined"&&module.exports)module.exports={providerEvidenceApi};
