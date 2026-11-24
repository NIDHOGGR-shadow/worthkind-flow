"use strict";
// Development reference UI. Uses API results and DOM textContent; never invents external fulfilment.
const qs=(s)=>document.querySelector(s);
let receipt=null;
let currentCase=null;
let pendingRequest=null;
let isSubmitting=false;
function freshRequest(base,slug){
  // Reuse both secrets for unchanged retries so a lost network response
  // cannot create a second case or strand the guest without a receipt.
  const snapshot=JSON.stringify({slug,...base});
  if(!pendingRequest || pendingRequest.snapshot!==snapshot){
    if(!globalThis.crypto?.getRandomValues)throw new Error("Secure random generation unavailable; contact hotel staff.");
    const hex=(count)=>Array.from(crypto.getRandomValues(new Uint8Array(count)),x=>x.toString(16).padStart(2,"0")).join("");
    pendingRequest={snapshot,request_key:hex(16),receipt_token:hex(32)};
  }
  return {...base,request_key:pendingRequest.request_key,receipt_token:pendingRequest.receipt_token};
}
function setStatus(el,text){el.textContent=text;}
function choose(kind){qs("#category").value=kind;qs("#new-request").scrollIntoView({behavior:"smooth"});}
for(const btn of document.querySelectorAll("[data-kind]"))btn.addEventListener("click",()=>choose(btn.dataset.kind));
qs("#human-bypass").addEventListener("click",()=>choose("human"));
qs("#check-intent").addEventListener("click",async()=>{
  const text=qs("#question").value.trim(),slug=qs("#hotel").value;
  if(!text){setStatus(qs("#routing-result"),"Enter a question first.");return;}
  try{
    const response=await fetch(`/api/properties/${encodeURIComponent(slug)}/route`,{
      method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({text})
    });
    if(!response.ok)throw new Error("Routing unavailable");
    const result=await response.json();
    if(result.intent==="information"){
      const infoResponse=await fetch("/api/properties/"+encodeURIComponent(slug)+"/information",{
        method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({question:text})
      });
      if(!infoResponse.ok)throw new Error("Hotel information unavailable");
      const info=await infoResponse.json();
      setStatus(qs("#routing-result"),info.status==="answered"
        ? info.answer+" (Synthetic demo source; no external AI used.)"
        : "There is no verified answer. Please use the human enquiry form.");
    }else{
      setStatus(qs("#routing-result"),"Identified: "+result.intent+". Next action: "+result.next_action.replaceAll("_"," ")+". No reservation or payment was made.");
    }
    const kinds=new Set(["human","booking","food","careers","supplier","events"]);
    if(kinds.has(result.intent))qs("#category").value=result.intent;
  }catch(err){setStatus(qs("#routing-result"),"Unable to route right now. Use the direct enquiry form or call hotel staff.");}
});
qs("#enquiry-form").addEventListener("submit",async(event)=>{
  event.preventDefault();
  if(isSubmitting)return;
  const out=qs("#submission-result");
  const slug=qs("#hotel").value;
  let payload;
  try{
    payload=freshRequest({
      kind:qs("#category").value,name:qs("#name").value.trim(),
      contact:qs("#contact").value.trim(),details:qs("#details").value.trim()
    },slug);
  }catch(error){setStatus(out,error.message);return;}
  const submitButton=qs("#enquiry-form button[type=submit]");
  isSubmitting=true;
  submitButton.disabled=true;
  setStatus(out,"Submitting enquiry...");
  try{
    const response=await fetch(`/api/properties/${encodeURIComponent(slug)}/enquiries`,{
      method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(payload)
    });
    const result=await response.json();
    if(!response.ok)throw new Error(result.detail||"Unable to submit");
    receipt=result.receipt_token || pendingRequest.receipt_token;
    currentCase={id:result.case_id,slug};
    setStatus(out,result.message);
    qs("#track").hidden=false;
    setStatus(qs("#receipt"),`Case ID: ${result.case_id}. Receipt token (keep private): ${receipt}`);
    setStatus(qs("#case-status"),`Status: ${result.status}. ${result.status==="queued"?"No staff has accepted it yet.":"Refresh to check the latest local response."}`);
    qs("#track").scrollIntoView({behavior:"smooth"});
  }catch(err){
    setStatus(out,`Submission not confirmed: ${err.message}. Retry the unchanged form when the connection returns; the same request key prevents duplicates. No booking or payment has been confirmed.`);
  }finally{
    isSubmitting=false;
    submitButton.disabled=false;
  }
});
qs("#refresh").addEventListener("click",async()=>{
  if(!currentCase||!receipt)return;
  try{
    const response=await fetch(`/api/properties/${currentCase.slug}/enquiries/${currentCase.id}`,{
      headers:{"X-Receipt-Token":receipt},cache:"no-store"
    });
    if(!response.ok)throw new Error("Could not check status");
    const result=await response.json();
    setStatus(qs("#case-status"),`Status: ${result.status}. ${result.staff_reply||"No staff response yet."}`);
  }catch(err){setStatus(qs("#case-status"),"Status unavailable. Try again or contact the hotel.");}
});

function renderCheckedReceipt(id,slug,token,status,reply){
  currentCase={id,slug};
  receipt=token;
  qs("#track").hidden=false;
  setStatus(qs("#receipt"),"Hotel: "+slug+"\nCase ID: "+id+"\nPrivate receipt token: "+token);
  setStatus(qs("#case-status"),"Status: "+status+". "+(reply||"No staff response recorded yet."));
  qs("#track").scrollIntoView({behavior:"smooth"});
}

// The receipt is deliberately not saved to localStorage, cookies, or the URL.
qs("#recover-form").addEventListener("submit",async(event)=>{
  event.preventDefault();
  const slug=qs("#recover-hotel").value;
  const id=qs("#recover-case-id").value.trim();
  const token=qs("#recover-token").value.trim();
  const output=qs("#recover-result");
  if(!id || token.length<32){
    setStatus(output,"Enter the original case ID and private receipt token.");
    return;
  }
  const button=qs("#recover-submit");
  button.disabled=true;
  setStatus(output,"Verifying your private receipt...");
  try{
    const response=await fetch(
      "/api/properties/"+encodeURIComponent(slug)+"/enquiries/"+encodeURIComponent(id),
      {method:"GET",headers:{"X-Receipt-Token":token},cache:"no-store"}
    );
    if(!response.ok)throw new Error("Receipt could not be verified.");
    const result=await response.json();
    if(result.case_id!==id || typeof result.status!=="string"){
      throw new Error("Unexpected response from the local server.");
    }
    setStatus(output,"Receipt verified locally. This does not mean a hotel has been contacted.");
    // Clear the entry widget after successful verification to limit extra copies.
    qs("#recover-token").value="";
    renderCheckedReceipt(id,slug,token,result.status,result.staff_reply);
  }catch(error){
    // Do not disclose whether an ID exists independently of its secret token.
    setStatus(output,"Could not verify this receipt. Check the hotel, case ID and token, then retry.");
  }finally{
    button.disabled=false;
  }
});

qs("#recover-toggle").addEventListener("click",()=>{
  const input=qs("#recover-token");
  const reveal=input.type==="password";
  input.type=reveal?"text":"password";
  qs("#recover-toggle").textContent=reveal?"Hide":"Show";
  qs("#recover-toggle").setAttribute("aria-label",reveal?"Hide private receipt token":"Show private receipt token");
  qs("#recover-toggle").setAttribute("aria-pressed",String(reveal));
});

qs("#copy-receipt").addEventListener("click",async()=>{
  if(!currentCase || !receipt)return;
  const content="Hotel: "+currentCase.slug+"\nCase ID: "+currentCase.id+"\nPrivate receipt token: "+receipt;
  if(!navigator.clipboard?.writeText){
    setStatus(qs("#case-status"),"Clipboard unavailable. Copy your case ID and receipt token manually from above.");
    return;
  }
  try{
    await navigator.clipboard.writeText(content);
    setStatus(qs("#case-status"),"Private receipt copied. Store it securely; do not share it publicly.");
  }catch{
    setStatus(qs("#case-status"),"Clipboard permission denied. Copy the private receipt manually from above.");
  }
});

qs("#new-enquiry").addEventListener("click",()=>{
  pendingRequest=null;
  receipt=null;
  currentCase=null;
  qs("#enquiry-form").reset();
  qs("#recover-form").reset();
  qs("#track").hidden=true;
  setStatus(qs("#submission-result"),"New request ready. This is a separate enquiry, not a booking.");
  setStatus(qs("#recover-result"),"No previous enquiry checked.");
  qs("#new-request").scrollIntoView({behavior:"smooth"});
});
