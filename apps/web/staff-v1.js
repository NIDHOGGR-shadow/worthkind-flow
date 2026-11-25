"use strict";
(() => {
  const el=id=>document.getElementById(id);
  const say=(id,message)=>{el(id).textContent=message;};
  const node=(tag,text,cls)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=String(text);if(cls)n.className=cls;return n;};
  const ctx=staffContext();
  let session,api,view="cases",cases=null,tickets=null,settings=null,pendingTicket=null,expiryTimer,authBusy=false;
  const randomKey=()=>Array.from(crypto.getRandomValues(new Uint8Array(16)),b=>b.toString(16).padStart(2,"0")).join("");
  const describe=s=>String(s).replaceAll("_"," ");
  function clearData(){
    cases=null;tickets=null;settings=null;
    el("v1-cases").replaceChildren();el("v1-tickets").replaceChildren();
    el("settings-form").hidden=true;say("settings-version","");say("ai-state","");
    el("guest-enabled").checked=false;
    say("case-summary","Load the server-authorized queue.");say("membership-result","");
    el("membership-form").reset();el("create-ticket").reset();
    pendingTicket=null;el("ticket-discard").hidden=true;
  }
  function controls(){
    const locked=ctx.busy||authBusy;
    el("login").disabled=!session||authBusy;
    el("signout").disabled=authBusy;
    el("staff-workspace").querySelectorAll("button,input,select,textarea").forEach(n=>{n.disabled=locked;});
    el("ticket-fields").disabled=locked||!!pendingTicket;
    el("ticket-create").textContent=pendingTicket?"Retry unchanged ticket":"Create ticket";
    el("ticket-discard").hidden=!pendingTicket;
  }
  function localExit(message){
    clearTimeout(expiryTimer);session?.clear();ctx.select("");clearData();
    el("staff-slug").value="";el("password").value="";el("email").value="";
    say("property-label","No hotel selected.");say("staff-message","");
    el("staff-workspace").hidden=true;el("login-panel").hidden=false;el("signout").hidden=true;
    say("login-status",message);controls();
  }
  function showView(value){
    view=value;
    document.querySelectorAll("[data-panel]").forEach(n=>{n.hidden=n.id!==value+"-view";});
    document.querySelectorAll("[data-view]").forEach(n=>n.setAttribute("aria-pressed",String(n.dataset.view===value)));
  }
  function renderCases(){
    const root=el("v1-cases");root.replaceChildren();if(!cases)return;
    const filtered=cases.cases.filter(c=>!el("case-filter").value||c.status===el("case-filter").value);
    say("case-summary",filtered.length+" of "+cases.cases.length+" returned cases · Role: "+cases.staff_role+" · Maximum 100 records");
    if(!filtered.length)root.append(node("p","No matching cases.","case-empty"));
    for(const c of filtered){
      const card=node("article",undefined,"staff-record");
      card.append(node("h3",c.customer_name||"Guest enquiry"),node("p",describe(c.kind)+" · "+describe(c.status)+" · "+c.id,"staff-meta"));
      if(c.contact)card.append(node("p",c.contact,"staff-meta"));
      card.append(node("p",c.details||"No request details returned."));
      if(c.status==="queued"){const b=node("button","Claim case","button primary");b.type="button";b.addEventListener("click",()=>mutate(()=>api.caseAction(ctx.slug,c.id,"claim"),loadCases,"Case claimed by server."));card.append(b);}
      if(c.status==="claimed"){
        const form=node("form"),label=node("label","Record a response"),field=node("textarea");field.id="reply-"+c.id;label.htmlFor=field.id;field.required=true;field.minLength=2;field.maxLength=3000;field.rows=3;
        const b=node("button","Record response","button primary");b.type="submit";form.append(label,field,b);
        form.addEventListener("submit",e=>{e.preventDefault();if(field.value.trim().length<2)return;mutate(()=>api.caseAction(ctx.slug,c.id,"respond",field.value.trim()),loadCases,"Response recorded. External delivery is not confirmed.");});card.append(form);
      }
      root.append(card);
    }
  }
  function renderTickets(){
    const root=el("v1-tickets");root.replaceChildren();if(!tickets)return;
    const filtered=tickets.filter(t=>(!el("ticket-filter").value||t.category===el("ticket-filter").value)&&(!el("ticket-status-filter").value||t.status===el("ticket-status-filter").value));
    if(!filtered.length)root.append(node("p","No matching department tickets.","case-empty"));
    for(const t of filtered){
      const card=node("article",undefined,"staff-record");
      card.append(node("h3",t.subject||"Department ticket"),node("p",describe(t.category)+" · "+describe(t.priority)+" · "+describe(t.status),"staff-meta"),node("p",t.description||"No description returned."),node("p","Ticket "+t.id,"staff-meta"));
      if(t.due_at)card.append(node("p","Due: "+t.due_at+(t.overdue?" · Overdue":""),t.overdue?"staff-overdue":"staff-meta"));
      if(t.assignee)card.append(node("p","Assigned identity: "+t.assignee,"staff-meta"));
      const allowed={open:["claim"],assigned:["start"],in_progress:["resolve"],resolved:["reopen"],reopened:["claim"]}[t.status]||[];
      const label=node("label","Work note (optional for state changes)"),field=node("textarea");field.id="note-"+t.id;label.htmlFor=field.id;field.rows=2;field.maxLength=1500;
      card.append(label,field);const row=node("div",undefined,"actions");
      for(const action of [...allowed,"note"]){
        const b=node("button",({claim:"Claim",start:"Start work",resolve:"Resolve",reopen:"Reopen",note:"Add note"})[action],"button secondary");b.type="button";
        b.addEventListener("click",()=>{const note=field.value.trim();if((action==="note"||note)&&note.length<4){say("staff-message","Enter a note of at least four characters.");return;}if(["resolve","reopen"].includes(action)&&!confirm("Confirm "+action+" for this ticket?"))return;mutate(()=>api.ticketAction(ctx.slug,t.id,action,note),loadTickets,"Ticket update confirmed by server. Notification delivery is not confirmed.");});row.append(b);
      }card.append(row);root.append(card);
    }
  }
  function renderSettings(){
    if(!settings)return;el("settings-form").hidden=false;el("guest-enabled").checked=settings.guest_enquiries_enabled;
    say("settings-version","Revision "+settings.revision);say("ai-state","AI: "+(settings.ai_enabled?"Enabled":"Disabled")+" · Reported setting only, not service readiness.");
  }
  async function run(op,apply,loading="Checking service…"){
    if(ctx.busy||authBusy)return false;
    if(!ctx.slug){say("staff-message","Select a hotel code first.");return false;}
    const stamp=ctx.stamp();say("staff-message",loading);
    try{const task=ctx.run(op);controls();const data=await task;if(!ctx.isCurrent(stamp)||!session.signedIn)return false;apply(data);return true;}
    catch(e){if(!ctx.isCurrent(stamp))return false;if(e.status===401){localExit("Session expired or rejected. Sign in again.");return false;}say("staff-message",e.message);return false;}
    finally{controls();}
  }
  async function loadCases(){
    cases=null;renderCases();return run(slug=>api.cases(slug),data=>{cases=data;renderCases();say("staff-message","Reception queue loaded from server.");});
  }
  async function loadTickets(){
    tickets=null;renderTickets();return run(slug=>api.tickets(slug),data=>{tickets=data;renderTickets();say("staff-message","Department tickets loaded from server.");});
  }
  async function loadSettings(){
    settings=null;el("settings-form").hidden=true;return run(slug=>api.settings(slug),data=>{settings=data;renderSettings();say("staff-message","Current settings loaded.");});
  }
  async function mutate(action,reload,copy){
    const stamp=ctx.stamp();const ok=await run(()=>action(),()=>say("staff-message",copy),"Submitting authorized action…");
    if(!ctx.isCurrent(stamp))return;
    // Always reload on an ambiguous or rejected transition: never repeat it automatically.
    const outcome=el("staff-message").textContent;
    const refreshed=await reload();
    if(ctx.isCurrent(stamp))say("staff-message",outcome+(refreshed?" Current records refreshed.":" Refresh unsuccessful; check before retrying."));
    return ok;
  }
  document.querySelectorAll("[data-view]").forEach(b=>b.addEventListener("click",()=>{if(!ctx.busy)showView(b.dataset.view);}));
  el("property-form").addEventListener("submit",e=>{
    e.preventDefault();if(ctx.busy)return;
    const slug=el("staff-slug").value.trim();
    if(!/^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(slug)||slug.length>100)return;
    if(pendingTicket&&!confirm("A ticket may already have been created. Switching property discards its local retry key. Continue?"))return;
    ctx.select(slug);clearData();say("property-label","Selected: "+slug+" · Access checked by each server request.");say("staff-message","Select a module and load its authorized records.");controls();
  });
  el("load-cases").addEventListener("click",loadCases);el("case-filter").addEventListener("change",renderCases);
  el("load-tickets").addEventListener("click",loadTickets);el("ticket-filter").addEventListener("change",renderTickets);el("ticket-status-filter").addEventListener("change",renderTickets);
  el("load-settings").addEventListener("click",loadSettings);
  el("settings-form").addEventListener("submit",async e=>{e.preventDefault();if(!settings||ctx.busy)return;const revision=settings.revision,enabled=el("guest-enabled").checked;if(!confirm("Change guest enquiry access for "+ctx.slug+"?"))return;await mutate(()=>api.updateSettings(ctx.slug,revision,enabled),loadSettings,"Settings update confirmed.");});
  el("create-ticket").addEventListener("submit",async e=>{
    e.preventDefault();if(ctx.busy||!ctx.slug)return;
    const body={category:el("ticket-category").value,priority:el("ticket-priority").value,subject:el("ticket-subject").value.trim(),description:el("ticket-description").value.trim()};
    const origin=el("ticket-origin").value.trim();if(origin)body.origin_case_id=origin;
    if(!pendingTicket){if(body.subject.length<4||body.description.length<8||(origin&&!WF_UUID.test(origin))){say("staff-message","Check the title, description and optional case ID.");return;}pendingTicket={...body,request_key:randomKey()};}
    const stamp=ctx.stamp();
    const ok=await run(slug=>api.createTicket(slug,pendingTicket),data=>{say("staff-message","Ticket "+data.ticket_id+" recorded. External delivery not confirmed.");pendingTicket=null;el("create-ticket").reset();},"Submitting ticket…");
    if(ok&&ctx.isCurrent(stamp)){const message=el("staff-message").textContent;await loadTickets();if(ctx.isCurrent(stamp))say("staff-message",message);}
    controls();
  });
  el("ticket-discard").addEventListener("click",()=>{if(!ctx.busy&&pendingTicket&&confirm("Discard the retry key? This does not cancel a server ticket.")){pendingTicket=null;controls();say("staff-message","Pending retry discarded locally.");}});
  async function membership(action){
    if(ctx.busy)return;const subject=el("member-subject").value.trim(),role=el("member-role").value;
    if(action==="revoke"&&!confirm("Revoke this identity's membership of "+ctx.slug+"?"))return;
    await run(slug=>api.membership(slug,action,subject,role),d=>{say("membership-result","Membership "+d.membership_id+" · "+d.role+" · "+d.state);say("staff-message","Membership command confirmed. No account or email delivery is implied.");if(action==="revoke"){cases=null;tickets=null;settings=null;renderCases();renderTickets();el("settings-form").hidden=true;}});
  }
  el("membership-form").addEventListener("submit",e=>{e.preventDefault();membership("invite");});el("accept-membership").addEventListener("click",()=>membership("accept"));el("revoke-membership").addEventListener("click",()=>membership("revoke"));
  el("login-form").addEventListener("submit",async e=>{
    e.preventDefault();if(authBusy||!session)return;authBusy=true;controls();say("login-status","Signing in…");const password=el("password").value;el("password").value="";
    try{await session.signIn(el("email").value.trim(),password);el("login-panel").hidden=true;el("staff-workspace").hidden=false;el("signout").hidden=false;showView("cases");expiryTimer=setTimeout(()=>localExit("Session expired. Sign in again."),Math.max(0,session.expiresAt-Date.now()));el("staff-slug").focus();}
    catch(e){say("login-status",e.message);}finally{authBusy=false;controls();}
  });
  el("signout").addEventListener("click",async()=>{if(authBusy)return;authBusy=true;const task=session.signOut();localExit("Signed out of this workspace.");const revoked=await task;authBusy=false;controls();if(!revoked)say("login-status","Signed out locally. Provider session revocation could not be confirmed.");});
  window.addEventListener("pagehide",()=>{clearTimeout(expiryTimer);session?.clear();ctx.select("");clearData();});
  window.addEventListener("pageshow",e=>{if(e.persisted)localExit("Sign in again to access staff records.");});
  (async()=>{try{const r=await fetch(new URL("./staff-auth-config.json",location.href),{cache:"no-store",credentials:"same-origin",redirect:"error"});if(!r.ok)throw staffError("Staff identity configuration unavailable.");session=staffSession(window.fetch.bind(window),await r.json());api=staffApi(window.fetch.bind(window),session);say("login-status","Sign in with your confirmed hotel identity.");}catch{say("login-status","Staff sign-in is unavailable until an authorized identity provider is configured.");}finally{controls();}})();
})();
