"use strict";
const byId=(s)=>document.getElementById(s);
function text(id,value){byId(id).textContent=value;}
byId("early-form").addEventListener("submit",async(event)=>{
  event.preventDefault();
  const form=event.currentTarget,button=byId("submit");
  if(!form.reportValidity())return;
  const rooms=byId("rooms").value.trim();
  const payload={
    hotel_name:byId("hotel").value.trim(),hotel_address:byId("address").value.trim()||null,
    area:byId("area").value.trim(),rooms_reported:rooms?Number(rooms):null,
    representative:byId("name").value.trim(),representative_role:byId("role").value,
    email:byId("email").value.trim(),workflow_challenge:byId("challenge").value,
    consent_early_access:byId("consent").checked,consent_marketing:byId("marketing").checked
  };
  button.disabled=true;text("result","Submitting request...");
  try{
    const resp=await fetch("/api/early-access",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(payload)});
    const result=await resp.json();
    if(!resp.ok)throw new Error(typeof result.detail==="string"?result.detail:"Request could not be recorded.");
    text("result",result.message+" Reference: "+result.reference+
      ". Private withdrawal token (save securely; not sent by email in preview): "+result.withdraw_token+
      ". Status: "+result.status+". NOT a confirmed pilot.");
    form.reset();
  }catch(e){text("result","Could not submit: "+e.message);}
  finally{button.disabled=false;}
});
byId("withdraw-form").addEventListener("submit",async(event)=>{
  event.preventDefault();
  const token=byId("withdraw-token").value.trim();
  if(!event.currentTarget.reportValidity())return;
  try{
    const resp=await fetch("/api/early-access/withdraw",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({token})});
    if(!resp.ok)throw new Error("Unable to process the request");
    const body=await resp.json();text("withdraw-result",body.message);
    byId("withdraw-token").value="";
  }catch(e){text("withdraw-result","Withdrawal failed; please retry in the preview.");}
});
