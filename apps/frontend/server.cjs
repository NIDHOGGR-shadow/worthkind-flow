"use strict";
const http=require("node:http");
const {readFile}=require("node:fs/promises");
const path=require("node:path");
const {staffConfig}=require("../web/staff-v1-core.js");
const WEB=path.resolve(__dirname,"../web");
const ASSETS=new Map([
 ["/","guest-v1.html"],["/staff","staff-v1.html"],
 ...["guest-v1.html","staff-v1.html","styles.css","guest-v1-core.js","guest-v1.js","staff-v1-core.js","staff-v1.js","commerce-core.js","guest-commerce.js","staff-commerce.js","management-core.js","staff-management.js","guest-management.js","native-booking-core.js","native-booking-guest.js","native-booking-staff.js","provider-evidence-core.js","provider-evidence-ui.js"].map(f=>["/static/"+f,f])
]);
const LIMIT=2_000_000, RESPONSE_LIMIT=8_000_000;
const UUID="[0-9a-fA-F-]{36}";
const allowed=[
 ["GET","/enquiries/"+UUID],["POST","/enquiries"],
 ["GET","/staff/cases"],["POST","/staff/cases/"+UUID+"/(?:claim|respond|control)"],
 ["GET","/staff/tickets"],["POST","/staff/tickets"],["GET","/staff/tickets/"+UUID],["POST","/staff/tickets/"+UUID+"/transition"],
 ["GET","/staff/settings"],["PUT","/staff/settings"],["POST","/staff/memberships/(?:invite|accept|revoke)"],
 ["GET","/staff/schedule"],["PUT","/staff/profiles/"+UUID],["POST","/staff/shifts"],["POST","/staff/shifts/"+UUID+"/cancel"],
 ["GET","/staff/rooms"],["PUT","/staff/rooms/"+UUID+"/state"],
 ["GET","/(?:content|rooms|menu|venues)"],
 ["GET","/guest/cases/"+UUID+"/reservation-intents"],["POST","/guest/cases/"+UUID+"/reservation-intents"],["POST","/guest/cases/"+UUID+"/reservation-intents/"+UUID+"/withdraw"],["POST","/guest/cases/"+UUID+"/venue-requests"],
 ["GET","/staff/reservation-intents"],["POST","/staff/reservation-intents/"+UUID+"/review"],
 ["GET","/staff/pms/availability"],["GET","/staff/pms/channel-reservations"],["PUT","/staff/room-types"],["POST","/staff/rooms"],["PUT","/staff/display-rates"],["PUT","/staff/menu"],["POST","/staff/venues"],["GET","/staff/pms/reservations/[A-Za-z0-9_-]{1,100}"],
 ["GET","/staff/dining/orders"],["POST","/staff/dining/orders"],["POST","/staff/dining/orders/"+UUID+"/transition"],
 ["GET","/staff/venue-requests"],["POST","/staff/venue-requests/"+UUID+"/decision"],
 ["GET","/staff/finance"],["POST","/staff/finance/invoices"],["POST","/staff/finance/invoices/"+UUID+"/checkout"],["POST","/staff/finance/payments/"+UUID+"/verify"],["POST","/staff/finance/refunds"],["POST","/staff/finance/refunds/"+UUID+"/(?:decision|submit|verify)"],
 ["GET","/staff/content"],["POST","/staff/content"],["POST","/staff/content/"+UUID+"/decision"],
 ["GET","/staff/procurement"],["GET","/staff/purchase-batches"],["POST","/staff/purchase-batches"],["POST","/staff/purchase-batches/"+UUID+"/decision"],["POST","/staff/stock/items"],["POST","/staff/suppliers"],["PUT","/staff/suppliers/"+UUID+"/state"],["POST","/staff/purchase-orders"],["POST","/staff/purchase-orders/"+UUID+"/decision"],["POST","/staff/stock/movements"],
 ["GET","/vacancies"],["POST","/staff/vacancies"],["POST","/staff/vacancies/"+UUID+"/decision"],["GET","/staff/applications"],["POST","/staff/applications/"+UUID+"/decision"],
 ["GET","/guest/cases/"+UUID+"/preferences"],["PUT","/guest/cases/"+UUID+"/preferences"],["POST","/guest/cases/"+UUID+"/feedback"],["POST","/guest/cases/"+UUID+"/consent"],["POST","/guest/cases/"+UUID+"/applications"],
 ["GET","/staff/pms/reservation-evidence"],["POST","/staff/pms/reservation-evidence"],["GET","/staff/pms/commands"],["POST","/staff/pms/commands/create"],["POST","/staff/pms/reservations/[A-Za-z0-9_-]{1,100}/commands"],["POST","/staff/pms/rate-commands"],["POST","/staff/pms/rate-commands/"+UUID+"/verify"],["GET","/staff/pos/reconciliation"],["POST","/staff/pos/orders/"+UUID+"/reconcile"],["GET","/staff/finance/settlements"],["GET","/staff/finance/settlements/[0-9]{1,20}/transactions"],["GET","/staff/feedback"],["POST","/staff/feedback/"+UUID+"/review"],
 ["GET","/native-availability"],["PUT","/staff/bookable-rates"],["GET","/staff/native-bookings"],["POST","/staff/native-bookings/holds"],["POST","/staff/native-bookings/"+UUID+"/cancel"],["GET","/staff/native-bookings/"+UUID+"/folio"],["POST","/staff/native-bookings/"+UUID+"/stay"],["POST","/staff/finance/stay-invoices"],["GET","/guest/cases/"+UUID+"/native-bookings"],["POST","/guest/cases/"+UUID+"/native-bookings/"+UUID+"/(?:confirm|change-dates)"]
].map(([method,suffix])=>[method,new RegExp("^/api/v1/properties/[a-z0-9]+(?:-[a-z0-9]+)*"+suffix+"$")]);
function config(env){
 const upstream=new URL(env.WF_FRONTEND_API_ORIGIN||"");
 if(upstream.protocol!=="https:"||upstream.username||upstream.password||upstream.pathname!=="/"||upstream.search||upstream.hash)throw Error("Configure an HTTPS backend origin, without path or credentials.");
 let identity={enabled:false,provider:"supabase"};
 if(env.WF_FRONTEND_AUTH_ENABLED==="1"){
   identity={enabled:true,provider:"supabase",url:env.WF_SUPABASE_URL,publishableKey:env.WF_SUPABASE_PUBLISHABLE_KEY};
   staffConfig(identity);
 }
 return {upstream:upstream.origin,identity};
}
function headers(identity){
 return {"Cache-Control":"no-store","X-Content-Type-Options":"nosniff","Referrer-Policy":"no-referrer","X-Frame-Options":"DENY",
 "Content-Security-Policy":"default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'"+(identity.enabled?" "+identity.url:"")+"; img-src 'self' data:; font-src 'self'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'",
 "Permissions-Policy":"camera=(), microphone=(), geolocation=()"};
}
function json(res,status,data,base){res.writeHead(status,{...base,"Content-Type":"application/json; charset=utf-8"});res.end(JSON.stringify(data));}
async function boundedBody(stream,max){
 if(!stream)return Buffer.alloc(0);
 const parts=[];let total=0;
 for await(const part of stream){const b=Buffer.from(part);total+=b.length;if(total>max)throw Error("Size limit exceeded");parts.push(b);}
 return Buffer.concat(parts,total);
}
function handler({upstream,identity},fetcher=fetch){
 const base=headers(identity);
 return async(req,res)=>{
   const raw=req.url||"";
   if(!raw.startsWith("/")||raw.startsWith("//")||raw.includes("\\")||raw.length>4096){json(res,400,{detail:"Invalid path"},base);return;}
   let url;try{url=new URL(raw,"http://frontend.invalid");}catch{json(res,400,{detail:"Invalid path"},base);return;}
   // Reject normalized traversal and encoded path separators; only allow exact public files.
   if(url.pathname!==raw.split("?")[0]||/%(?:2f|5c|2e)/i.test(url.pathname)){json(res,404,{detail:"Not found"},base);return;}
   const method=req.method;
   if(["GET","HEAD"].includes(method)){
     if(url.pathname==="/health"){json(res,200,{status:"ok",scope:"frontend_only"},base);return;}
     if(["/staff-auth-config.json","/static/staff-auth-config.json"].includes(url.pathname)){json(res,200,identity,base);return;}
     const file=ASSETS.get(url.pathname);
     if(file){try{const body=await readFile(path.join(WEB,file));const type=file.endsWith(".html")?"text/html":file.endsWith(".css")?"text/css":"text/javascript";res.writeHead(200,{...base,"Content-Type":type+"; charset=utf-8","Content-Length":body.length});res.end(method==="HEAD"?undefined:body);}catch{json(res,503,{detail:"Frontend asset unavailable"},base);}return;}
   }
   if(!allowed.some(([m,re])=>m===method&&re.test(url.pathname))){json(res,404,{detail:"Not found"},base);return;}
   // No cookie forwarding, arbitrary destination, legacy API, or client-controlled upstream headers.
   const h={Accept:"application/json"};
   for(const k of ["authorization","x-receipt-token","content-type"]){if(typeof req.headers[k]==="string")h[k]=req.headers[k];}
   if(method!=="GET"&&h["content-type"]&&!/^application\/json(?:;|$)/i.test(h["content-type"])){json(res,415,{detail:"JSON required"},base);return;}
   if(Number(req.headers["content-length"]||0)>LIMIT){json(res,413,{detail:"Request too large"},base);return;}
   let body;try{if(method!=="GET")body=await boundedBody(req,LIMIT);}catch{if(!res.destroyed)json(res,413,{detail:"Request too large"},base);return;}
   try{
     const response=await fetcher(upstream+url.pathname+url.search,{method,headers:h,...(body?.length?{body}:{}),redirect:"manual",signal:AbortSignal.timeout(20000)});
     if(response.status>=300&&response.status<400){await response.body?.cancel();json(res,502,{detail:"Unexpected upstream redirect"},base);return;}
     const data=await boundedBody(response.body,RESPONSE_LIMIT);
     if(!/application\/json/i.test(response.headers.get("content-type")||"")){json(res,502,{detail:"Unexpected upstream response"},base);return;}
     // Only JSON is served from upstream on this origin; strip all upstream cookies/redirects.
     JSON.parse(data.toString("utf8"));res.writeHead(response.status,{...base,"Content-Type":"application/json; charset=utf-8"});res.end(data);
   }catch{if(!res.headersSent)json(res,503,{detail:"Service unavailable; action outcome unconfirmed"},base);else res.destroy();}
 };
}
if(require.main===module){const port=Number(process.env.PORT||8080);http.createServer({requestTimeout:30000,headersTimeout:10000},handler(config(process.env))).listen(port,"0.0.0.0");}
module.exports={config,handler};
