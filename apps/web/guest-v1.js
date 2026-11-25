"use strict";
(() => {
  const el=id=>document.getElementById(id);
  const api=guestApi(window.fetch.bind(window));
  const randomHex=n=>Array.from(crypto.getRandomValues(new Uint8Array(n)),b=>b.toString(16).padStart(2,"0")).join("");
  const journey=createGuestJourney(api,randomHex);
  const commerce=initGuestCommerce(journey);
  const management=initGuestManagement(journey,commerce);
  const say=(id,msg)=>{el(id).textContent=msg;};
  const statusText={queued:"Recorded — waiting for staff acceptance",claimed:"Accepted by staff",responded:"Staff response recorded",escalated:"Escalated for staff review",resolved:"Marked resolved by staff — guest confirmation not recorded"};
  function controls(){
    el("request-fields").disabled=journey.busy||journey.pending||!!journey.active;
    el("recover-fields").disabled=journey.busy||journey.pending||!!journey.active;
    el("v1-submit").disabled=journey.busy||!!journey.active;
    el("v1-submit").textContent=journey.pending?"Retry unchanged request":"Send request";
    el("v1-discard").hidden=!journey.pending;
    el("v1-discard").disabled=journey.busy;
    el("v1-recover").disabled=journey.busy||journey.pending||!!journey.active;
    el("v1-refresh").disabled=journey.busy||!journey.active;
    el("v1-new").disabled=journey.busy||commerce.busy||management.busy;
    document.querySelectorAll("[data-service]").forEach(b=>{b.disabled=journey.busy||journey.pending||!!journey.active;});
  }
  function render(result,focus){
    const active=journey.active;
    commerce.activate();management.activate();
    el("v1-track").hidden=false;
    say("v1-case-status",statusText[result.status]+". No reservation, payment or external notification is confirmed.");
    say("v1-reply",typeof result.staff_reply==="string"?result.staff_reply:"No staff response returned yet.");
    say("v1-receipt","Hotel: "+active.slug+"\nCase ID: "+active.case_id+"\nPrivate receipt token: "+active.token);
    if(focus){el("v1-receipt").hidden=true;el("v1-reveal").setAttribute("aria-expanded","false");say("v1-reveal","Show private receipt");el("track-heading").focus();}
  }
  document.querySelectorAll("[data-service]").forEach(b=>b.addEventListener("click",()=>{if(journey.busy||journey.pending||journey.active)return;el("v1-kind").value=b.dataset.service;el("v1-hotel").focus();}));
  el("v1-form").addEventListener("submit",async e=>{
    e.preventDefault();if(journey.busy||journey.active)return;
    const fields={kind:el("v1-kind").value,name:el("v1-name").value.trim(),contact:el("v1-contact").value.trim(),details:el("v1-details").value.trim()};
    const slug=el("v1-hotel").value.trim();
    if(!/^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(slug)||fields.name.length<2||fields.contact.length<5||fields.details.length<8){say("v1-submit-status","Check the hotel code and required details.");return;}
    say("v1-submit-status","Submitting your request…");
    try{const task=journey.submit(slug,fields);controls();const result=await task;say("v1-submit-status","Request recorded by the server.");render(result,true);}
    catch(err){say("v1-submit-status",err.message+(journey.pending?" Keep this page open and retry unchanged, or explicitly discard the pending request.":""));}
    finally{controls();}
  });
  el("v1-recover-form").addEventListener("submit",async e=>{
    e.preventDefault();if(journey.busy||journey.pending||journey.active)return;
    say("v1-recover-status","Checking receipt…");
    try{const task=journey.recover(el("recover-slug").value.trim(),el("recover-id").value.trim(),el("recover-proof").value.trim());controls();const result=await task;el("recover-proof").value="";say("v1-recover-status","Receipt verified.");render(result,true);}
    catch(err){say("v1-recover-status",err.message);}
    finally{controls();}
  });
  el("v1-refresh").addEventListener("click",async()=>{
    if(journey.busy||commerce.busy||!journey.active)return;
    say("v1-case-status","Checking latest status…");
    try{const task=journey.refresh();controls();render(await task,false);}
    catch(err){say("v1-case-status",err.message+" The previous state is not newly verified.");}
    finally{controls();}
  });
  el("v1-reveal").addEventListener("click",()=>{const reveal=el("v1-receipt").hidden;el("v1-receipt").hidden=!reveal;el("v1-reveal").setAttribute("aria-expanded",String(reveal));say("v1-reveal",reveal?"Hide private receipt":"Show private receipt");});
  el("v1-discard").addEventListener("click",()=>{
    if(journey.busy||!journey.pending)return;
    if(!window.confirm("The hotel may already have received this request. Discarding its retry proof could leave you unable to recover it. Continue?"))return;
    journey.reset();say("v1-submit-status","Unconfirmed request discarded locally. This did not cancel a server record.");controls();
  });
  el("v1-new").addEventListener("click",()=>{
    if(journey.busy||commerce.busy||!journey.active)return;
    if((commerce.pending||management.pending)&&!window.confirm("An unconfirmed stay, venue, feedback or application request may exist. Starting over discards its local retry proof. Continue?"))return;
    if(!window.confirm("Have you saved the private receipt? Starting over removes it from this page."))return;
    journey.reset();commerce.reset();management.reset();el("v1-form").reset();el("v1-recover-form").reset();el("v1-track").hidden=true;el("v1-receipt").hidden=true;say("v1-receipt","");say("v1-reply","");say("v1-case-status","");say("v1-recover-status","");say("v1-submit-status","Ready for a new request.");controls();el("v1-hotel").focus();
  });
  controls();
})();
