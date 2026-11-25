"use strict";
(() => {
  const el=id=>document.getElementById(id);
  const say=(id,message)=>{el(id).textContent=message;};
  const node=(tag,text,cls)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=String(text);if(cls)n.className=cls;return n;};
  const ctx=staffContext();
  let roster=null,rooms=null,range=null;
  let session,api,view="cases",cases=null,tickets=null,settings=null,pendingTicket=null,expiryTimer,authBusy=false;
  const randomKey=()=>Array.from(crypto.getRandomValues(new Uint8Array(16)),b=>b.toString(16).padStart(2,"0")).join("");
  const describe=s=>String(s).replaceAll("_"," ");
  const commerce=initStaffCommerce({session:()=>session,ctx,run,mutate});
  const management=initStaffManagement({session:()=>session,ctx,run,mutate});
  const native=initNativeStaff({session:()=>session,ctx,run,mutate});
  const evidence=initProviderEvidence({session:()=>session,ctx,run,mutate});
  function clearData(){
    commerce.clear();management.clear();native.clear();evidence.clear();
    roster=null;rooms=null;range=null;el("staff-roster").replaceChildren();el("staff-shifts").replaceChildren();el("staff-rooms").replaceChildren();el("staff-profile-form").reset();el("shift-form").reset();el("schedule-range").reset();
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
    commerce.controls();management.controls();native.controls();
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
      const allowed={claimed:["transfer","escalate"],responded:["transfer","escalate","resolve"],escalated:["transfer","resolve"]}[c.status]||[];
      if(allowed.length){
        const box=node("details"),summary=node("summary","Case controls"),label=node("label","Reason (required)"),reason=node("textarea");
        reason.id="reason-"+c.id;label.htmlFor=reason.id;reason.minLength=8;reason.maxLength=1500;reason.rows=2;
        box.append(summary,label,reason);
        let target;
        if(allowed.includes("transfer")){
          const tl=node("label","Transfer to membership ID");target=node("input");target.id="target-"+c.id;target.maxLength=36;tl.htmlFor=target.id;box.append(tl,target);
        }
        const actions=node("div",undefined,"actions");
        for(const action of allowed){
          const b=node("button",({transfer:"Transfer",escalate:"Escalate",resolve:"Mark resolved by staff"})[action],"button secondary");b.type="button";
          b.addEventListener("click",()=>{const why=reason.value.trim(),to=target?.value.trim();if(why.length<8||(action==="transfer"&&!WF_UUID.test(to))){say("staff-message","Enter a valid reason and transfer membership ID when required.");return;}if(!confirm("Confirm "+action+" for this case? Staff resolution is not guest confirmation."))return;mutate(()=>api.caseControl(ctx.slug,c.id,action,why,to),loadCases,"Case control recorded. No guest confirmation or notification delivery is implied.");});actions.append(b);
        }box.append(actions);card.append(box);
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
      const history=node("div"),historyButton=node("button","Load ticket history","button secondary");
      historyButton.type="button";history.setAttribute("aria-live","polite");
      historyButton.addEventListener("click",async()=>{
        history.replaceChildren();
        await run(slug=>api.ticketDetail(slug,t.id),detail=>{
          if(detail.origin_case_id)history.append(node("p","Linked enquiry: "+detail.origin_case_id,"staff-meta"));
          history.append(node("h4","Activity history"));
          if(!detail.history.length)history.append(node("p","No history returned."));
          for(const event of detail.history){
            const entry=node("div",undefined,"ticket-history-entry");
            entry.append(node("p",describe(event.action)+" · "+dateLabel(event.created_at),"staff-meta"));
            if(event.actor)entry.append(node("p","Actor: "+event.actor,"staff-meta"));
            if(event.note)entry.append(node("p",event.note));
            history.append(entry);
          }
          say("staff-message","Authorized ticket history loaded.");
        });
      });card.append(historyButton,history);
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
    catch(e){if(!ctx.isCurrent(stamp))return false;if(e.status===401){localExit("Session expired or rejected. Sign in again.");return false;}if(e.status===403){commerce.clear();management.clear();native.clear();evidence.clear();roster=null;rooms=null;renderSchedule();renderRooms();cases=null;tickets=null;settings=null;renderCases();renderTickets();el("settings-form").hidden=true;say("case-summary","Access must be verified again.");say("membership-result","");}say("staff-message",e.message);return false;}
    finally{controls();}
  }
  async function loadCases(){
    cases=null;renderCases();say("case-summary","No verified queue loaded.");return run(slug=>api.cases(slug),data=>{cases=data;renderCases();say("staff-message","Reception queue loaded from server.");});
  }
  async function loadTickets(){
    tickets=null;renderTickets();return run(slug=>api.tickets(slug),data=>{tickets=data;renderTickets();say("staff-message","Department tickets loaded from server.");});
  }
  function iso(value){const d=new Date(value);if(!Number.isFinite(d.getTime()))throw staffError("Select a valid date and time.");return d.toISOString();}
  function dateLabel(value){const d=new Date(value);return Number.isFinite(d.getTime())?d.toLocaleString():String(value);}
  function renderSchedule(){
    const root=el("staff-roster"),shifts=el("staff-shifts");root.replaceChildren();shifts.replaceChildren();if(!roster)return;
    if(!roster.members.length)root.append(node("p","No authorized staff records returned.","case-empty"));
    for(const m of roster.members){
      const card=node("article",undefined,"staff-record");
      card.append(node("h3",m.display_name||"Staff member"),node("p",describe(m.role)+" · "+describe(m.state),"staff-meta"),node("p",m.job_title||"No job title recorded."),node("p","Membership: "+m.membership_id,"staff-meta"));
      if(m.state==="active"){const b=node("button","Use for profile or shift","button secondary");b.type="button";b.addEventListener("click",()=>{el("profile-member").value=m.membership_id;el("profile-name").value=m.display_name||"";el("profile-title").value=m.job_title||"";el("profile-reference").value=m.employee_reference||"";el("shift-member").value=m.membership_id;});card.append(b);}root.append(card);
    }
    if(!roster.shifts.length)shifts.append(node("p","No shifts returned for this range.","case-empty"));
    for(const shift of roster.shifts){
      const card=node("article",undefined,"staff-record"),member=roster.members.find(m=>m.membership_id===shift.membership_id);
      card.append(node("h3",member?.display_name||shift.membership_id),node("p",dateLabel(shift.starts_at)+" to "+dateLabel(shift.ends_at)),node("p",shift.state,"staff-meta"));
      if(shift.state==="scheduled"){const b=node("button","Cancel shift","button secondary");b.type="button";b.addEventListener("click",()=>{if(confirm("Cancel this scheduled shift?"))mutate(()=>api.cancelShift(ctx.slug,shift.id),loadSchedule,"Shift cancellation recorded.");});card.append(b);}shifts.append(card);
    }
  }
  async function loadSchedule(){if(!range){say("staff-message","Select a schedule date range first.");return false;}roster=null;renderSchedule();return run(slug=>api.schedule(slug,range.start,range.end),data=>{roster=data;renderSchedule();say("staff-message","Authorized roster and shifts loaded.");});}
  function renderRooms(){
    const root=el("staff-rooms");root.replaceChildren();if(!rooms)return;
    const filtered=rooms.filter(r=>!el("room-filter").value||r.operational_state===el("room-filter").value);
    if(!filtered.length)root.append(node("p","No matching room records.","case-empty"));
    for(const r of filtered){
      const card=node("article",undefined,"staff-record");card.append(node("h3",r.label),node("p",describe(r.operational_state)+" · Revision "+r.revision,"staff-meta"));
      const label=node("label","Operational condition"),select=node("select");select.id="room-"+r.id;label.htmlFor=select.id;
      for(const state of ["unknown","clean","dirty","inspecting","out_of_service"]){const o=node("option",describe(state));o.value=state;select.append(o);}select.value=r.operational_state;
      const b=node("button","Update room condition","button secondary");b.type="button";b.addEventListener("click",()=>{if(select.value===r.operational_state)return;if(confirm("Update the operational condition of "+r.label+"?"))mutate(()=>api.roomState(ctx.slug,r.id,select.value,r.revision),loadRooms,"Room condition updated. Occupancy and availability are not verified.");});card.append(label,select,b);root.append(card);
    }
  }
  async function loadRooms(){rooms=null;renderRooms();return run(slug=>api.rooms(slug),data=>{rooms=data;renderRooms();say("staff-message","Room conditions loaded. Occupancy is not verified.");});}
  el("schedule-range").addEventListener("submit",e=>{e.preventDefault();if(ctx.busy)return;try{range={start:iso(el("schedule-start").value),end:iso(el("schedule-end").value)};loadSchedule();}catch(e){say("staff-message",e.message);}});
  el("staff-profile-form").addEventListener("submit",async e=>{e.preventDefault();if(ctx.busy)return;const member=el("profile-member").value.trim(),body={display_name:el("profile-name").value.trim(),job_title:el("profile-title").value.trim(),employee_reference:el("profile-reference").value.trim()};if(!WF_UUID.test(member)||Object.values(body).some(x=>x.length<2)){say("staff-message","Enter a valid membership and profile.");return;}const ok=await mutate(()=>api.saveProfile(ctx.slug,member,body),loadSchedule,"Staff profile saved.");if(ok)el("staff-profile-form").reset();});
  el("shift-form").addEventListener("submit",async e=>{e.preventDefault();if(ctx.busy)return;try{const member=el("shift-member").value.trim(),start=iso(el("shift-start").value),end=iso(el("shift-end").value);const ok=await mutate(()=>api.createShift(ctx.slug,member,start,end),loadSchedule,"Shift scheduled by server.");if(ok)el("shift-form").reset();}catch(e){say("staff-message",e.message);}});
  el("load-rooms").addEventListener("click",loadRooms);el("room-filter").addEventListener("change",renderRooms);
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
    if((pendingTicket||commerce.pending||management.pending||native.pending)&&!confirm("An unconfirmed ticket, dining order, stock operation or room hold may already exist. Switching property discards its local retry key. Continue?"))return;
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
    await run(slug=>api.membership(slug,action,subject,role),d=>{say("membership-result","Membership "+d.membership_id+" · "+d.role+" · "+d.state);say("staff-message","Membership command confirmed. No account or email delivery is implied.");if(action==="revoke"){commerce.clear();management.clear();native.clear();evidence.clear();roster=null;rooms=null;renderSchedule();renderRooms();cases=null;tickets=null;settings=null;renderCases();renderTickets();el("settings-form").hidden=true;}});
  }
  el("membership-form").addEventListener("submit",e=>{e.preventDefault();membership("invite");});el("accept-membership").addEventListener("click",()=>membership("accept"));el("revoke-membership").addEventListener("click",()=>membership("revoke"));
  el("login-form").addEventListener("submit",async e=>{
    e.preventDefault();if(authBusy||!session)return;authBusy=true;controls();say("login-status","Signing in…");const password=el("password").value;el("password").value="";
    try{await session.signIn(el("email").value.trim(),password);el("login-panel").hidden=true;el("staff-workspace").hidden=false;el("signout").hidden=false;showView("cases");expiryTimer=setTimeout(()=>localExit("Session expired. Sign in again."),Math.max(0,session.expiresAt-Date.now()));el("staff-slug").focus();}
    catch(e){say("login-status",e.message);}finally{authBusy=false;controls();}
  });
  el("signout").addEventListener("click",async()=>{if(authBusy)return;if((pendingTicket||commerce.pending||management.pending||native.pending)&&!confirm("A ticket, dining order, stock operation or room hold is unconfirmed. Signing out discards its local retry key, not the server record. Continue?"))return;authBusy=true;const task=session.signOut();localExit("Signed out of this workspace.");const revoked=await task;authBusy=false;controls();if(!revoked)say("login-status","Signed out locally. Provider session revocation could not be confirmed.");});
  window.addEventListener("pagehide",()=>{clearTimeout(expiryTimer);session?.clear();ctx.select("");clearData();});
  window.addEventListener("pageshow",e=>{if(e.persisted)localExit("Sign in again to access staff records.");});
  (async()=>{try{const r=await fetch(new URL("./staff-auth-config.json",location.href),{cache:"no-store",credentials:"same-origin",redirect:"error"});if(!r.ok)throw staffError("Staff identity configuration unavailable.");session=staffSession(window.fetch.bind(window),await r.json());api=staffApi(window.fetch.bind(window),session);say("login-status","Sign in with your confirmed hotel identity.");}catch{say("login-status","Staff sign-in is unavailable until an authorized identity provider is configured.");}finally{controls();}})();
})();
