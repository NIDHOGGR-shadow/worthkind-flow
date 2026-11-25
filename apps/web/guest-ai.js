"use strict";
(()=>{const el=id=>document.getElementById(id),api=aiStudioApi(window.fetch.bind(window));let busy=false,epoch=0;
const clear=()=>{++epoch;el("guest-ai-answer").replaceChildren();el("guest-ai-result").textContent="";};
el("guest-ai-hotel").addEventListener("input",clear);
el("guest-ai-form").addEventListener("submit",async e=>{e.preventDefault();if(busy)return;clear();const stamp=epoch,slug=el("guest-ai-hotel").value.trim(),q=el("guest-ai-question").value.trim(),consent=el("guest-ai-consent").checked;busy=true;el("guest-ai-submit").disabled=true;el("guest-ai-result").textContent="Checking approved hotel information…";try{const d=await api.chat(slug,q,consent);if(stamp!==epoch)return;renderApprovedAi(el("guest-ai-answer"),d);el("guest-ai-result").textContent=d.status==="answered"?"Approved information returned.":"Please use the human contact route.";el("guest-ai-question").value="";el("guest-ai-consent").checked=false;}catch(e){if(stamp===epoch)el("guest-ai-result").textContent=e.message+" Use the human enquiry route below.";}finally{busy=false;el("guest-ai-submit").disabled=false;}});
window.addEventListener("pagehide",()=>{clear();el("guest-ai-form").reset();});
})();
