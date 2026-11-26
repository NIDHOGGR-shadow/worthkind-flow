"use strict";
(() => {
  const el=id=>document.getElementById(id);
  const api=guestApi(window.fetch.bind(window));
  const randomHex=n=>Array.from(crypto.getRandomValues(new Uint8Array(n)),b=>b.toString(16).padStart(2,"0")).join("");
  const journey=createGuestJourney(api,randomHex);
  const commerce=initGuestCommerce(journey,()=>management.busy||native.busy);
  const management=initGuestManagement(journey,commerce,()=>native.busy);
  const native=initNativeGuest(journey,()=>commerce.busy||management.busy);
  const say=(id,msg)=>{el(id).textContent=msg;};
  const publicViews=new Set(["home","hotel-catalog","request","recover","guest-careers","guest-ai","guest-voice"]);
  const privateViews=new Set(["v1-track","guest-commerce","native-guest","guest-records"]);
  const page=el("home");
  function showView(requested,focus=false,historyMode="push"){
    let view=publicViews.has(requested)||privateViews.has(requested)?requested:"home";
    if(privateViews.has(view)&&!journey.active)view="recover";
    if(journey.active&&(view==="request"||view==="recover"))view="v1-track";
    page.dataset.guestView=view;
    el("guest-journey-bar").hidden=!journey.active;
    say("guest-journey-hotel",journey.active?.slug||"");
    const nav=document.querySelector(".guest-nav a[href='#recover']");
    if(nav)nav.setAttribute("aria-current",privateViews.has(view)||view==="recover"?"page":"false");
    document.querySelectorAll(".guest-nav a,.guest-journey-bar a").forEach(a=>{
      const target=a.getAttribute("href").slice(1);
      a.setAttribute("aria-current",target===view||(target==="recover"&&privateViews.has(view))?"page":"false");
    });
    if(historyMode!=="none"&&location.hash!=="#"+view){history[historyMode==="replace"?"replaceState":"pushState"](null,"","#"+view);}
    if(focus){const target=view==="home"?page.querySelector("h1"):el(view).querySelector("h2");if(target){target.tabIndex=-1;target.focus({preventScroll:true});}window.scrollTo({top:0,behavior:"instant"});}
    if(journey.active){for(const id of ["catalog-slug","vacancy-hotel","guest-ai-hotel","voice-hotel"]){if(!el(id).value)el(id).value=journey.active.slug;}}
  }
  document.addEventListener("click",e=>{const link=e.target.closest("a[href^='#']");if(!link||e.defaultPrevented||e.ctrlKey||e.metaKey||e.shiftKey||e.altKey)return;const view=link.getAttribute("href").slice(1);if(publicViews.has(view)||privateViews.has(view)){e.preventDefault();showView(view,true);}});
  window.addEventListener("popstate",()=>showView(location.hash.slice(1),true,"replace"));
  window.addEventListener("hashchange",()=>showView(location.hash.slice(1),true,"replace"));
  document.addEventListener("flow:guest-view",e=>showView(e.detail,true));
  document.addEventListener("flow:human-handoff",e=>{if(journey.busy||journey.pending)return;const {slug,question}=e.detail||{};if(journey.active){showView("v1-track",true);say("receipt-copy-status","You have an existing request. Save its receipt and start a new request if you need further help.");return;}showView("request",true);const hotel=el("v1-hotel"),details=el("v1-details");if(hotel.value.trim()&&slug&&hotel.value.trim()!==slug){say("v1-submit-status","Review your existing draft and hotel before sending. Nothing was sent.");return;}if(typeof slug==="string"&&/^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(slug)&&slug.length<=100)hotel.value=slug;el("v1-kind").value="human";if(!details.value.trim()&&typeof question==="string"&&question.length<=800)details.value=question;say("v1-submit-status","Review your request and contact details, then send it to reception. Nothing has been sent yet.");el("v1-name").focus();});
  const statusText={queued:"Recorded — waiting for staff acceptance",claimed:"Accepted by staff",responded:"Staff response recorded",escalated:"Escalated for staff review",resolved:"Marked resolved by staff — guest confirmation not recorded"};
  function controls(){
    el("request-fields").disabled=journey.busy||journey.pending||!!journey.active;
    el("recover-fields").disabled=journey.busy||journey.pending||!!journey.active;
    el("v1-submit").disabled=journey.busy||!!journey.active;
    el("v1-submit").textContent=journey.pending?"Retry unchanged request":"Send request";
    el("v1-discard").hidden=!journey.pending;
    el("v1-discard").disabled=journey.busy;
    el("v1-recover").disabled=journey.busy||journey.pending||!!journey.active;
    el("v1-refresh").disabled=journey.busy||commerce.busy||management.busy||native.busy||!journey.active;
    el("v1-new").disabled=journey.busy||commerce.busy||management.busy||native.busy;
    document.querySelectorAll("[data-service]").forEach(b=>{b.disabled=journey.busy||journey.pending;const active=!!journey.active;if(b.dataset.service==="human")b.textContent=active?"View my request":"Contact reception";else{const text=b.querySelector("span:not(.service-arrow)");if(text){if(!text.dataset.original)text.dataset.original=text.textContent;text.textContent=active?(["booking","events"].includes(b.dataset.service)?"Manage your stay and venue requests":"View your current request or start a new one"):text.dataset.original;}}});
  }
  function render(result,focus){
    const active=journey.active;
    commerce.activate();management.activate();native.activate();
    el("v1-track").hidden=false;
    say("v1-case-status",statusText[result.status]+". This enquiry status does not establish booking, payment or notification status.");
    say("v1-reply",typeof result.staff_reply==="string"?result.staff_reply:"No staff response returned yet.");
    say("v1-receipt","Hotel: "+active.slug+"\nCase ID: "+active.case_id+"\nPrivate receipt token: "+active.token);
    if(focus){el("v1-receipt").hidden=true;el("v1-copy").hidden=true;say("receipt-copy-status","");el("v1-reveal").setAttribute("aria-expanded","false");say("v1-reveal","Show private receipt");showView("v1-track",true);}
  }
  document.querySelectorAll("[data-service]").forEach(b=>b.addEventListener("click",()=>{if(journey.busy||journey.pending)return;if(journey.active){showView(["booking","events"].includes(b.dataset.service)?"guest-commerce":"v1-track",true);return;}el("v1-kind").value=b.dataset.service;showView("request",true);el("v1-hotel").focus();}));
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
    if(journey.busy||commerce.busy||management.busy||native.busy||!journey.active)return;
    say("v1-case-status","Checking latest status…");
    try{const task=journey.refresh();controls();render(await task,false);}
    catch(err){say("v1-case-status",err.message+" The previous state is not newly verified.");}
    finally{controls();}
  });
  el("v1-reveal").addEventListener("click",()=>{const reveal=el("v1-receipt").hidden;el("v1-receipt").hidden=!reveal;el("v1-copy").hidden=!reveal;say("receipt-copy-status","");el("v1-reveal").setAttribute("aria-expanded",String(reveal));say("v1-reveal",reveal?"Hide private receipt":"Show private receipt");});
  el("v1-copy").addEventListener("click",async()=>{const active=journey.active;if(!active||el("v1-receipt").hidden)return;try{if(!navigator.clipboard?.writeText)throw Error("Clipboard unavailable");await navigator.clipboard.writeText(el("v1-receipt").textContent);if(journey.active?.slug===active.slug&&journey.active?.case_id===active.case_id&&journey.active?.token===active.token&&!el("v1-receipt").hidden)say("receipt-copy-status","Receipt copied. Keep it confidential.");}catch{if(journey.active?.slug===active.slug&&journey.active?.case_id===active.case_id&&journey.active?.token===active.token&&!el("v1-receipt").hidden)say("receipt-copy-status","Clipboard unavailable. Select and copy the visible receipt manually.");}});
  el("v1-discard").addEventListener("click",()=>{
    if(journey.busy||!journey.pending)return;
    if(!window.confirm("The hotel may already have received this request. Discarding its retry proof could leave you unable to recover it. Continue?"))return;
    journey.reset();say("v1-submit-status","Unconfirmed request discarded locally. This did not cancel a server record.");controls();
  });
  el("v1-new").addEventListener("click",()=>{
    if(journey.busy||commerce.busy||management.busy||native.busy||!journey.active)return;
    if((commerce.pending||management.pending)&&!window.confirm("An unconfirmed stay, venue, feedback or application request may exist. Starting over discards its local retry proof. Continue?"))return;
    if(!window.confirm("Have you saved the private receipt? Starting over removes it from this page."))return;
    journey.reset();commerce.reset();management.reset();native.reset();el("v1-form").reset();el("v1-recover-form").reset();el("v1-track").hidden=true;el("v1-receipt").hidden=true;el("v1-copy").hidden=true;say("receipt-copy-status","");el("v1-reveal").setAttribute("aria-expanded","false");say("v1-reveal","Show private receipt");say("v1-receipt","");say("v1-reply","");say("v1-case-status","");say("v1-recover-status","");say("v1-submit-status","Ready for a new request.");controls();showView("request",true);el("v1-hotel").focus();
  });
  controls();showView(location.hash.slice(1),false,location.hash?"replace":"none");
})();
