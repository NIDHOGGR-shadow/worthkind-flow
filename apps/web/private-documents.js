"use strict";
function privateDocumentApi(fetcher,session){
 const uuid=/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
 const max=2000000;
 const invalid=()=>{throw Error("Invalid document or unexpected response.");};
 async function call(slug,method,path,body){
  if(typeof slug!=="string"||slug.length>100||!/^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(slug))invalid();
  const headers={Authorization:"Bearer "+session.token(),Accept:method==="GET"?"application/octet-stream":"application/json"};
  if(body)headers["Content-Type"]="application/octet-stream";
  let r;try{r=await fetcher("/api/v1/properties/"+encodeURIComponent(slug)+"/staff/documents"+path,{method,headers,...(body?{body}:{}),cache:"no-store",credentials:"same-origin",redirect:"error"});}catch{throw Error("Connection interrupted; upload outcome may be unknown. Do not blindly repeat.");}
  if(!r.ok)throw Object.assign(Error(({401:"Session rejected.",403:"Document access denied.",404:"Document unavailable.",413:"Document exceeds 2 MB.",503:"Document service unavailable or outcome unknown."})[r.status]||"Document request not confirmed."),{status:r.status});
  return r;
 }
 return {
  async upload(slug,file){if(!file||!Number.isSafeInteger(file.size)||file.size<1||file.size>max)invalid();const r=await call(slug,"POST","",file);const d=await r.json();if(!uuid.test(d?.document_id)||d.size!==file.size)invalid();return d;},
  async download(slug,id){if(typeof id!=="string"||!uuid.test(id))invalid();const r=await call(slug,"GET","/"+id);if(r.headers.get("content-type")!=="application/octet-stream"||!/^attachment(?:;|$)/i.test(r.headers.get("content-disposition")||""))invalid();const b=await r.blob();if(!b.size||b.size>max)invalid();return b;}
 };
}
function initPrivateDocuments({session,ctx,run}){
 const el=id=>document.getElementById(id),api=privateDocumentApi(window.fetch.bind(window),{token:()=>session().token()});
 const say=t=>{el("documents-result").textContent=t;};
 let url=null,uncertain=false;
 function revoke(){if(url){URL.revokeObjectURL(url);url=null;}el("document-download-link").hidden=true;el("document-download-link").removeAttribute("href");}
 function clear(){revoke();uncertain=false;el("document-upload").reset();el("document-download").reset();say("");controls();}
 function controls(){el("document-upload-submit").disabled=ctx.busy||uncertain;el("document-upload-clear").hidden=!uncertain;el("document-file").disabled=ctx.busy||uncertain;el("document-download-submit").disabled=ctx.busy;}
 el("document-upload-clear").addEventListener("click",()=>{if(ctx.busy||!confirm("Confirm you have investigated the previous upload. A new upload may create another stored document."))return;uncertain=false;el("document-upload").reset();say("Local upload block cleared. No server document was deleted.");controls();});
 el("document-upload").addEventListener("submit",async e=>{e.preventDefault();if(ctx.busy||uncertain||!ctx.slug)return;const file=el("document-file").files[0];if(!file||file.size<1||file.size>2000000){say("Select a nonempty file up to 2 MB.");return;}if(!confirm("Upload this private document to the selected hotel? Only authorized staff may retrieve it. Malware screening is not confirmed."))return;revoke();const stamp=ctx.stamp();uncertain=true;const ok=await run(s=>api.upload(s,file),d=>{uncertain=false;el("document-upload").reset();el("document-id").value=d.document_id;say("Server recorded "+d.size+" bytes. Save document ID "+d.document_id+"; there is no document listing or automatic recovery API.");});if(!ok&&ctx.isCurrent(stamp))say("Upload not confirmed. Do not repeat until investigated.");controls();});
 el("document-download").addEventListener("submit",async e=>{e.preventDefault();if(ctx.busy||!ctx.slug)return;revoke();const id=el("document-id").value.trim();await run(s=>api.download(s,id),b=>{url=URL.createObjectURL(b);const link=el("document-download-link");link.href=url;link.download="private-document-"+id+".bin";link.hidden=false;say("Authorized document received. Download as an attachment only. Scan locally before opening.");});});
 window.addEventListener("pagehide",revoke);
 return {clear,controls,get pending(){return uncertain;}};
}
if(typeof module!=="undefined"&&module.exports)module.exports={privateDocumentApi};
