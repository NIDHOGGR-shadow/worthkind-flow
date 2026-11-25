"use strict";
const COM_UUID=/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const COM_INTENTS=["requested","under_review","declined","withdrawn"];
const COM_DINING=["submitted","accepted","preparing","ready","served","rejected","cancelled"];
function commerceApi(fetcher,session){
 const fail=(message,status=0)=>Object.assign(Error(message),{status});
 const valid=(v)=>{if(!v)throw fail("Unexpected service response. Check the current records.");};
 const id=v=>{valid(typeof v==="string"&&COM_UUID.test(v));return v;};
 const key=v=>{valid(typeof v==="string"&&/^[A-Za-z0-9_-]{8,100}$/.test(v));return v;};
 const arr=(d,k,check)=>{valid(Array.isArray(d?.[k])&&d[k].every(check));return d[k];};
 const money=r=>Number.isSafeInteger(r?.amount_minor??r?.price_minor??r?.total_minor)&&(r.amount_minor??r.price_minor??r.total_minor)>=0&&/^[A-Z]{3}$/.test(r.currency);
 const record=r=>r&&typeof r.id==="string"&&COM_UUID.test(r.id)&&typeof r.state==="string";
 const date=v=>typeof v==="string"&&/^\d{4}-\d{2}-\d{2}$/.test(v)&&Number.isFinite(Date.parse(v))&&new Date(v).toISOString().slice(0,10)===v;
 const stay=(start,end)=>valid(date(start)&&date(end)&&Date.parse(end)>Date.parse(start)&&Date.parse(end)-Date.parse(start)<=90*86400000);
 const integer=(n,min,max)=>Number.isInteger(n)&&n>=min&&n<=max;
 async function call(slug,path,method="GET",body,access="public",token){
   valid(typeof slug==="string"&&slug.length<=100&&/^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(slug));
   const headers={Accept:"application/json"};
   if(access==="staff")headers.Authorization="Bearer "+session.token();
   if(access==="guest"){valid(typeof token==="string"&&/^[A-Za-z0-9_-]{32,128}$/.test(token));headers["X-Receipt-Token"]=token;}
   if(body!==undefined)headers["Content-Type"]="application/json";
   let r;try{r=await fetcher("/api/v1/properties/"+encodeURIComponent(slug)+path,{method,headers,...(body===undefined?{}:{body:JSON.stringify(body)}),cache:"no-store",credentials:"same-origin",redirect:"error"});}catch{throw fail("Connection interrupted; outcome not confirmed. Check records before repeating.");}
   if(!r.ok)throw fail(({401:"Session rejected. Sign in again.",403:"Access denied.",404:"Record unavailable.",409:"Conflict. Reload before retrying.",422:"Check the submitted details.",429:"Rate limit reached.",503:"Service unavailable or outcome unknown. Reconcile before retrying."})[r.status]||"Service did not confirm the operation.",r.status);
   try{return await r.json();}catch{throw fail("Unreadable service response.");}
 }
 const staff=(s,p,m,b)=>call(s,"/staff"+p,m,b,"staff");
 const guest=(a,p,m,b)=>call(a.slug,"/guest/cases/"+id(a.case_id)+p,m,b,"guest",a.token);
 const intent=r=>record(r)&&COM_INTENTS.includes(r.state);
 const order=r=>record(r)&&COM_DINING.includes(r.state)&&money(r);
 const result=(d,expected,state)=>{valid(record(d)&&(!expected||d.id===expected)&&(!state||d.state===state));return d;};
 return {
   async menu(s){return arr(await call(s,"/menu"),"items",x=>COM_UUID.test(x.id)&&typeof x.name==="string"&&money(x));},
   async catalog(s){const [c,r,m,v]=await Promise.all([call(s,"/content"),call(s,"/rooms"),call(s,"/menu"),call(s,"/venues")]);return {content:arr(c,"content",x=>typeof x.key==="string"&&x.content&&typeof x.content.title==="string"&&typeof x.content.body==="string"),rooms:arr(r,"rooms",x=>COM_UUID.test(x.id)&&typeof x.name==="string"&&integer(x.max_guests,1,30)),menu:arr(m,"items",x=>COM_UUID.test(x.id)&&typeof x.name==="string"&&money(x)),venues:arr(v,"venues",x=>COM_UUID.test(x.id)&&typeof x.name==="string"&&integer(x.capacity,1,100000))};},
   async intents(a){const d=await guest(a,"/reservation-intents");valid(d.booking_confirmed===false&&d.inventory_held===false);return arr(d,"intents",intent);},
   async requestStay(a,b){stay(b.arrival,b.departure);valid(integer(b.adults,1,30)&&integer(b.children,0,30)&&integer(b.room_count,1,10));key(b.request_key);if(b.room_type_id)id(b.room_type_id);const d=await guest(a,"/reservation-intents","POST",b);valid(intent(d)&&d.booking_confirmed===false&&d.inventory_held===false);return d;},
   async withdraw(a,i){const d=await guest(a,"/reservation-intents/"+id(i)+"/withdraw","POST");valid(d.booking_confirmed===false);return result(d,i,"withdrawn");},
   async requestVenue(a,b){id(b.venue_id);key(b.request_key);const n=Date.parse(b.ends_at)-Date.parse(b.starts_at);valid(n>0&&n<=7*86400000&&integer(b.attendance,1,100000));return result(await guest(a,"/venue-requests","POST",b),null,"requested");},
   async reservationQueue(s){return arr(await staff(s,"/reservation-intents"),"intents",intent);},
   async reviewStay(s,i,action){valid(["review","decline"].includes(action));const d=await staff(s,"/reservation-intents/"+id(i)+"/review","POST",{action});valid(d.booking_confirmed===false);return result(d,i,action==="review"?"under_review":"declined");},
   async diningQueue(s){return arr(await staff(s,"/dining/orders"),"orders",order);},
   async createOrder(s,b){key(b.request_key);if(b.room_id)id(b.room_id);valid(Array.isArray(b.lines)&&b.lines.length>=1&&b.lines.length<=50&&new Set(b.lines.map(x=>x.item_id)).size===b.lines.length&&b.lines.every(x=>COM_UUID.test(x.item_id)&&integer(x.quantity,1,100)));const d=await staff(s,"/dining/orders","POST",b);valid(order(d)&&d.payment_confirmed===false);return d;},
   async diningAction(s,i,action){const states={accept:"accepted",prepare:"preparing",ready:"ready",serve:"served",reject:"rejected",cancel:"cancelled"};valid(Object.hasOwn(states,action));const d=await staff(s,"/dining/orders/"+id(i)+"/transition","POST",{action});valid(d.payment_confirmed===false);return result(d,i,states[action]);},
   async venueQueue(s){return arr(await staff(s,"/venue-requests"),"requests",r=>record(r)&&["requested","reviewed","accepted","declined","cancelled"].includes(r.state));},
   async venueAction(s,i,action){const states={review:"reviewed",accept:"accepted",decline:"declined",cancel:"cancelled"};valid(Object.hasOwn(states,action));return result(await staff(s,"/venue-requests/"+id(i)+"/decision","POST",{action}),i,states[action]);},
   async availability(s,b){stay(b.start,b.end);valid(integer(b.rooms,1,10)&&integer(b.adults,1,30)&&integer(b.children,0,30));const d=await staff(s,"/pms/availability?"+new URLSearchParams(b));valid(d.provider==="cloudbeds"&&d.inventory_held===false&&d.rates_binding===false&&typeof d.retrieved_at==="string");return {retrieved_at:d.retrieved_at,rooms:arr(d,"room_types",r=>typeof r.room_type_id==="string"&&Number.isSafeInteger(r.rooms_available)&&r.rooms_available>=0)};},
   async pmsReservation(s,ref){valid(typeof ref==="string"&&/^[A-Za-z0-9_-]{1,100}$/.test(ref));const d=await staff(s,"/pms/reservations/"+encodeURIComponent(ref));valid(d.provider==="cloudbeds"&&d.reservation?.reservation_id===ref&&typeof d.retrieved_at==="string"&&["confirmed","not_confirmed","canceled","checked_in","checked_out","no_show","in_progress"].includes(d.reservation.state));return d;},
   async finance(s){const d=await staff(s,"/finance");return {invoices:arr(d,"invoices",r=>record(r)&&money(r)),payments:arr(d,"payments",r=>record(r)&&money(r)&&["test","live"].includes(r.mode)),refunds:arr(d,"refunds",r=>record(r)&&Number.isSafeInteger(r.amount_minor)),exceptions:arr(d,"exceptions",record)};},
   async invoice(s,i){const d=await staff(s,"/finance/invoices","POST",{dining_order_id:id(i)});valid(COM_UUID.test(d?.id)&&d.source==="hotel_dining_order");return d;},
   async checkout(s,i,email){valid(typeof email==="string"&&/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)&&email.length<=254);const d=await staff(s,"/finance/invoices/"+id(i)+"/checkout","POST",{email});valid(record(d)&&["test","live"].includes(d.mode)&&typeof d.reference==="string"&&d.payment_confirmed===(d.state==="verified"&&d.mode==="live"));if(d.checkout_url!==null&&d.checkout_url!==undefined){let u;try{u=new URL(d.checkout_url);}catch{throw fail("Invalid payment link.");}valid(u.origin==="https://checkout.paystack.com"&&!u.username&&!u.password&&d.state==="pending");}return d;},
   async verify(s,i){const d=result(await staff(s,"/finance/payments/"+id(i)+"/verify","POST"),i);valid(["test","live"].includes(d.mode)&&d.payment_confirmed===(d.mode==="live"&&d.state==="verified"));return d;},
   async refund(s,i,reason){valid(typeof reason==="string"&&reason.length>=8&&reason.length<=240);return result(await staff(s,"/finance/refunds","POST",{payment_id:id(i),reason}),null,"requested");},
   async refundAction(s,i,action){valid(["approve","decline","submit","verify"].includes(action));const d=result(await staff(s,"/finance/refunds/"+id(i)+"/"+(["approve","decline"].includes(action)?"decision":action),"POST",["approve","decline"].includes(action)?{action}:undefined),i);if(["submit","verify"].includes(action))valid(["test","live"].includes(d.mode));return d;}
 };
}
if(typeof module!=="undefined"&&module.exports)module.exports={commerceApi};
