"use strict";
function capabilityMessage(info, caps) {
  if (!info || typeof info.name !== "string" || !info.name.trim() || !caps || typeof caps.mode !== "string") throw new Error("Invalid property response");
  if (caps.mode === "enquiry_only") return "Booking enquiries only. Room availability, payment and reservations are not confirmed here.";
  return "Reservation capability reported by the hotel service. This page supports enquiries only; staff must confirm availability and payment.";
}
function createPropertyController({select, name, status, load, fetcher}) {
  let generation=0;
  let controller;
  async function refresh() {
    const current=++generation;
    controller?.abort();
    controller=typeof AbortController==="function"?new AbortController():null;
    const slug=select.value;
    name.textContent="Selected hotel";
    status.textContent="Checking hotel information…";
    status.dataset.state="loading";
    load.disabled=true;
    try {
      const base="/api/properties/"+encodeURIComponent(slug);
      const options={cache:"no-store",...(controller?{signal:controller.signal}:{})};
      const responses=await Promise.all([fetcher(base,options),fetcher(base+"/booking-capabilities",options)]);
      if(responses.some(r=>!r.ok)) throw new Error("Property check failed");
      const [info,caps]=await Promise.all(responses.map(r=>r.json()));
      if(current!==generation || select.value!==slug) return;
      if(info.slug!==slug) throw new Error("Property mismatch");
      const copy=capabilityMessage(info,caps);
      name.textContent=info.name;
      status.textContent=copy;
      status.dataset.state="ready";
    }catch{
      if(current!==generation || select.value!==slug) return;
      status.textContent="Hotel information unavailable. You can still submit an enquiry; delivery is confirmed only by the server.";
      status.dataset.state="error";
    }finally{
      if(current===generation) load.disabled=false;
    }
  }
  select.addEventListener("change",refresh);
  load.addEventListener("click",refresh);
  return {refresh};
}
if (typeof module !== "undefined" && module.exports) {
  module.exports={capabilityMessage,createPropertyController};
} else {
  const select=document.querySelector("#hotel");
  const name=document.querySelector("#property-name");
  const status=document.querySelector("#property-capability");
  const load=document.querySelector("#refresh-property");
  if(select&&name&&status&&load) {
    const context=createPropertyController({select,name,status,load,fetcher:window.fetch.bind(window)});
    select.form?.addEventListener("reset",()=>queueMicrotask(context.refresh));
    context.refresh();
  }
}
