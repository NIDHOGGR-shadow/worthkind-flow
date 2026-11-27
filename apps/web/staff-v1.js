"use strict";
(() => {
  const el=id=>document.getElementById(id);
  const say=(id,message)=>{el(id).textContent=message;};
  const node=(tag,text,cls)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=String(text);if(cls)n.className=cls;return n;};
  const ctx=staffContext();
  let roster=null,rooms=null,range=null,propertyRows=[],propertyCursor=null;
  let attendanceRows=[],attendanceCursor=null,attendanceRange=null,leaveRows=[],leaveCursor=null,pendingLeave=null;
  let handoverRows=[],handoverPeople=[],handoverCursor=null,peopleCursor=null,pendingHandover=null;
  let replyDrafts=new Map();
  let session,api,view="cases",cases=null,tickets=null,settings=null,selectedCase=null,pendingTicket=null,expiryTimer,authBusy=false;
  const randomKey=()=>Array.from(crypto.getRandomValues(new Uint8Array(16)),b=>b.toString(16).padStart(2,"0")).join("");
  const describe=s=>String(s).replaceAll("_"," ");
  const commerce=initStaffCommerce({session:()=>session,ctx,run,mutate});
  const management=initStaffManagement({session:()=>session,ctx,run,mutate,navigate:showView});
  const native=initNativeStaff({session:()=>session,ctx,run,mutate});
  const evidence=initProviderEvidence({session:()=>session,ctx,run,mutate});
  const documents=initPrivateDocuments({session:()=>session,ctx,run});
  const aiStudio=initAiStudio({session:()=>session,ctx,run});
  function clearData(){replyDrafts.clear();clearWorkforce();clearHandovers();
    commerce.clear();management.clear();native.clear();evidence.clear();documents.clear();aiStudio.clear();
    roster=null;rooms=null;range=null;el("staff-roster").replaceChildren();el("staff-shifts").replaceChildren();el("staff-rooms").replaceChildren();el("staff-profile-form").reset();el("shift-form").reset();el("schedule-range").reset();renderStaffSelectors();
    cases=null;tickets=null;settings=null;selectedCase=null;el("case-search").value="";el("ticket-search").value="";say("ticket-summary","");el("case-filter").value="";el("ticket-filter").value="";el("ticket-status-filter").value="";
    el("v1-cases").replaceChildren();el("v1-tickets").replaceChildren();
    el("settings-form").hidden=true;say("settings-version","");say("ai-state","");
    el("guest-enabled").checked=false;
    say("case-summary","Refresh to see guest requests.");say("membership-result","");
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
    workforceControls(locked);handoverControls(locked);commerce.controls();management.controls();native.controls();evidence.controls();documents.controls();aiStudio.controls();
  }
  function clearProperties(){propertyRows=[];propertyCursor=null;el("property-discovery-list").replaceChildren();el("property-more").hidden=true;say("property-discovery-status","Find properties linked to your account.");}
  function localExit(message){clearProperties();
    clearTimeout(expiryTimer);session?.clear();ctx.select("");clearData();
    el("staff-slug").value="";el("password").value="";el("email").value="";
    say("workspace-title","Staff workspace");say("property-label","No hotel selected.");say("staff-message","");
    el("staff-workspace").hidden=true;el("login-panel").hidden=false;el("signout").hidden=true;
    say("login-status",message);controls();
  }
  function showView(value){
    if(view!==value&&!ctx.busy){say("staff-message","");say("ai-studio-result","");}
    view=value;
    el("staff-module-select").value=value;
    document.querySelectorAll("[data-panel]").forEach(n=>{n.hidden=n.id!==value+"-view";});
    document.querySelectorAll("[data-view]").forEach(n=>n.setAttribute("aria-pressed",String(n.dataset.view===value)));
    say("staff-current-module","Selected module: "+el("staff-module-select").selectedOptions[0].textContent);
  }
  el("staff-module-select").addEventListener("change",e=>{if(!ctx.busy&&Array.from(document.querySelectorAll("[data-view]")).some(n=>n.dataset.view===e.target.value))showView(e.target.value);});
  function renderCases(){
    const root=el("v1-cases");root.replaceChildren();renderHandoverCases();if(!cases)return;
    const q=el("case-search").value.trim().toLowerCase();
    const filtered=cases.cases.filter(c=>(!el("case-filter").value||c.status===el("case-filter").value)&&(!q||[c.customer_name,c.id,c.kind,c.details].some(v=>typeof v==="string"&&v.toLowerCase().includes(q))));
    say("case-summary",filtered.length+" of "+cases.cases.length+" returned cases · Role: "+cases.staff_role+" · Maximum 100 records");
    if(!filtered.length)root.append(node("p","No matching cases.","case-empty"));
    if(!filtered.length){selectedCase=null;return;}
    if(!filtered.some(c=>c.id===selectedCase))selectedCase=filtered[0].id;
    const list=node("div",undefined,"communication-list"),detail=node("div",undefined,"communication-detail");
    list.setAttribute("aria-label","Guest requests");root.append(list,detail);
    for(const c of filtered){const entry=node("button",undefined,"communication-entry");entry.type="button";entry.setAttribute("aria-pressed",String(c.id===selectedCase));entry.append(node("strong",c.customer_name||"Guest enquiry"),node("span",describe(c.kind)+" · "+describe(c.status),"staff-meta"),node("span",(c.details||"Guest request").slice(0,100),"communication-preview"));entry.addEventListener("click",()=>{if(ctx.busy)return;selectedCase=c.id;renderCases();const heading=detailHeading();if(heading)heading.focus();});list.append(entry);}
    function detailHeading(){return root.querySelector(".communication-detail h3");}
    for(const c of filtered.filter(c=>c.id===selectedCase)){
      const card=node("article",undefined,"staff-record communication-thread");
      const heading=node("h3",c.customer_name||"Guest enquiry");heading.tabIndex=-1;card.append(heading,node("p",describe(c.kind)+" · "+describe(c.status),"staff-meta"));
      if(c.contact)card.append(node("p",c.contact,"staff-meta"));
      const message=node("div",undefined,"communication-message");message.append(node("p","Guest request","communication-author"),node("p",c.details||"No request details returned."));card.append(message);
      if(typeof c.staff_reply==="string"&&c.staff_reply.trim()){const reply=node("div",undefined,"communication-message staff-reply");reply.append(node("p","Latest recorded staff response","communication-author"),node("p",c.staff_reply));card.append(reply);}
      if(c.status==="resolved"){const closure=node("div",undefined,"communication-message");closure.append(node("p","Guest confirmation","communication-author"));const status=node("p","Check whether the guest confirmed resolution.");const b=node("button","Check guest confirmation","button secondary");b.type="button";b.addEventListener("click",()=>{if(ctx.busy)return;run(slug=>api.resolution(slug,c.id),d=>{status.textContent=d.guest_confirmed?"Guest confirmed resolution.":d.awaiting_guest_confirmation?"Awaiting guest confirmation.":d.guest_decision==="reopen"?"Guest reopened this request. Refresh your inbox.":"No confirmation recorded.";});});closure.append(status,b);card.append(closure);}
      if(["responded","escalated","resolved"].includes(c.status)){
        const box=node("details"),title=node("summary","Service email notifications"),root=node("div");box.append(title,node("p","Delivery states come from the notification service. Queueing requires verified contact evidence and guest consent."),root);
        const refresh=node("button","Refresh notification records","button secondary");refresh.type="button";box.insertBefore(refresh,root);
        const labels={not_queued:"Not queued",pending:"Queued, not sent",accepted:"Provider accepted, delivery unconfirmed",delivered:"Provider reports delivered",failed:"Delivery failed",unknown:"Delivery outcome unknown",suppressed:"Suppressed"};
        async function load(){if(ctx.busy)return;await run(slug=>api.notifications(slug,c.id),rows=>{root.replaceChildren();if(!rows.length)root.append(node("p","No eligible service events returned."));for(const n of rows){const entry=node("article",undefined,"staff-record");entry.append(node("h4",n.event_type==="case_responded"?"Staff response":"Staff resolution"),node("p",dateLabel(n.created_at),"staff-meta"),node("p",labels[n.state]));if(n.state==="not_queued"){const form=node("form"),label=node("label","Contact verification reference"),field=node("input"),send=node("button","Queue service email","button secondary");field.id="email-evidence-"+n.event_id;label.htmlFor=field.id;field.required=true;field.minLength=8;field.maxLength=240;field.autocomplete="off";send.type="submit";form.append(label,field,send);form.addEventListener("submit",async e=>{e.preventDefault();if(ctx.busy||field.value.trim().length<8||!confirm("Queue this service email using the verified contact reference? The server checks the guest's consent."))return;const ok=await run(slug=>api.queueNotification(slug,c.id,n.event_id,field.value.trim()),d=>say("staff-message",labels[d.state]+". Verify the delivery record before reporting success."));if(ok)await load();});entry.append(form);}root.append(entry);}},"Refreshing notification records…");}
        refresh.addEventListener("click",load);card.append(box);
      }
      const ref=node("details"),refTitle=node("summary","Request reference");ref.append(refTitle,node("p",c.id,"staff-meta"));card.append(ref);
      const ticketButton=node("button","Create linked department task","button secondary");ticketButton.type="button";ticketButton.addEventListener("click",()=>{if(ctx.busy||pendingTicket)return;if(["ticket-subject","ticket-description","ticket-origin"].some(id=>el(id).value.trim())&&!confirm("Replace your unfinished department task draft?"))return;el("create-ticket").reset();el("ticket-origin").value=c.id;el("ticket-subject").value=("Guest request: "+describe(c.kind)).slice(0,160);el("ticket-description").value=(c.details||"Follow up on this guest request.").slice(0,3000);el("ticket-category").value="reception";showView("tickets");el("create-ticket").closest("details").open=true;el("ticket-subject").focus();say("staff-message","Review the department and share only the details needed to complete this task.");});card.append(ticketButton);
      if(c.status!=="resolved"){const handover=node("button","Prepare handover","button secondary");handover.type="button";handover.addEventListener("click",()=>{if(ctx.busy||pendingHandover)return;el("handover-panel").open=true;renderHandoverCases();el("handover-case").value=c.id;el("handover-note").focus();});card.append(handover);}
      if(c.status==="queued"){const b=node("button","Claim case","button primary");b.type="button";b.addEventListener("click",()=>mutate(()=>api.caseAction(ctx.slug,c.id,"claim"),loadCases,"Case claimed by server."));card.append(b);}
      if(c.status==="claimed"){
        const form=node("form"),label=node("label","Record a response"),field=node("textarea");field.id="reply-"+c.id;label.htmlFor=field.id;field.required=true;field.minLength=2;field.maxLength=3000;field.rows=3;field.value=replyDrafts.get(c.id)||"";field.addEventListener("input",()=>replyDrafts.set(c.id,field.value));
        const b=node("button","Record response","button primary");b.type="submit";form.append(label,field,b);
        form.addEventListener("submit",async e=>{e.preventDefault();if(ctx.busy||field.value.trim().length<2)return;const ok=await run(slug=>api.caseAction(slug,c.id,"respond",field.value.trim()),()=>{replyDrafts.delete(c.id);say("staff-message","Response recorded. External delivery is not confirmed.");});if(ok)await loadCases();});card.append(form);
      }
      const allowed={claimed:["transfer","escalate"],responded:["transfer","escalate","resolve"],escalated:["transfer","resolve"]}[c.status]||[];
      if(allowed.length){
        const box=node("details"),summary=node("summary","Case controls"),label=node("label","Reason (required)"),reason=node("textarea");
        reason.id="reason-"+c.id;label.htmlFor=reason.id;reason.minLength=8;reason.maxLength=1500;reason.rows=2;
        box.append(summary,label,reason);
        let target;
        if(allowed.includes("transfer")){
          const tl=node("label","Transfer to");target=node("select");target.id="target-"+c.id;tl.htmlFor=target.id;target.append(new Option("Choose a colleague",""));box.append(tl,target);
          const hint=node("p","Transfer is limited to active reception staff and managers. A listed colleague is not necessarily available.","staff-meta");
          const load=node("button","Find colleagues","button secondary");load.type="button";box.append(load,hint);
          let cursor=null;load.addEventListener("click",async()=>{if(ctx.busy)return;if(!cursor)target.replaceChildren(new Option("Choose a colleague",""));await run(slug=>api.handoverRecipients(slug,cursor),data=>{
            for(const m of data.recipients){if(![...target.options].some(o=>o.value===m.membership_id))target.append(new Option((m.display_name||"Staff "+m.membership_id.slice(0,8))+" · "+describe(m.role),m.membership_id));}
            cursor=data.next_cursor;load.textContent=cursor?"Find more colleagues":"Refresh colleagues";hint.textContent=target.options.length>1?"Choose an eligible colleague. Availability is not confirmed.":"No eligible colleagues returned. Escalate to a manager instead.";
          },"Loading eligible colleagues…");});
          const advanced=node("details"),advancedTitle=node("summary","Use a known staff reference"),manual=node("input"),manualLabel=node("label","Membership reference");manual.id="target-ref-"+c.id;manual.maxLength=36;manual.autocomplete="off";manualLabel.htmlFor=manual.id;advanced.append(advancedTitle,manualLabel,manual);box.append(advanced);target.addEventListener("change",()=>{manual.value="";});manual.addEventListener("input",()=>{target.value="";});target.manual=manual;
        }
        const actions=node("div",undefined,"actions");
        for(const action of allowed){
          const b=node("button",({transfer:"Transfer",escalate:"Escalate",resolve:"Mark resolved by staff"})[action],"button secondary");b.type="button";
          b.addEventListener("click",()=>{const why=reason.value.trim(),to=(target?.value||target?.manual?.value||"").trim();if(why.length<8||(action==="transfer"&&!WF_UUID.test(to))){say("staff-message","Enter a reason and choose an authorized colleague or known staff reference.");return;}if(!confirm("Confirm "+action+" for this case? Staff resolution is not guest confirmation."))return;mutate(()=>api.caseControl(ctx.slug,c.id,action,why,to),loadCases,"Case control recorded. No guest confirmation or notification delivery is implied.");});actions.append(b);
        }box.append(actions);card.append(box);
      }
      detail.append(card);
    }
  }

  function handoverControls(locked=ctx.busy||authBusy){el("handover-fields").disabled=locked||!!pendingHandover;el("handover-submit").textContent=pendingHandover?"Retry unchanged handover":"Send handover";el("handover-discard").hidden=!pendingHandover;el("handover-more").hidden=!handoverCursor;el("handover-recipients-more").hidden=!peopleCursor;}
  function clearHandovers(){handoverRows=[];handoverPeople=[];handoverCursor=null;peopleCursor=null;pendingHandover=null;el("handover-form").reset();el("handover-pending").checked=true;el("handover-list").replaceChildren();el("handover-recipient").replaceChildren(new Option("Find colleagues first",""));el("handover-case").replaceChildren(new Option("General shift note",""));say("handover-result","");handoverControls();}
  function renderHandoverCases(){const select=el("handover-case"),previous=select.value;select.replaceChildren(new Option("General shift note",""));for(const c of cases?.cases||[]){if(c.status!=="resolved")select.append(new Option(describe(c.kind)+" · "+describe(c.status)+" · "+c.id.slice(0,8),c.id));}if([...select.options].some(o=>o.value===previous))select.value=previous;}
  function renderHandoverPeople(){const select=el("handover-recipient"),previous=select.value;select.replaceChildren(new Option("Choose colleague",""));for(const p of handoverPeople)select.append(new Option((p.display_name||"Staff "+p.membership_id.slice(0,8))+" · "+describe(p.role),p.membership_id));if([...select.options].some(o=>o.value===previous))select.value=previous;}
  async function loadHandoverPeople(more=false){if(ctx.busy||pendingHandover)return;const cursor=more?peopleCursor:null;if(more&&!cursor)return;await run(slug=>api.handoverRecipients(slug,cursor),data=>{const map=new Map((more?handoverPeople:[]).map(p=>[p.membership_id,p]));for(const p of data.recipients)map.set(p.membership_id,p);handoverPeople=[...map.values()];peopleCursor=data.next_cursor;renderHandoverPeople();renderHandovers();say("handover-result",handoverPeople.length?"Eligible colleagues loaded. Availability is not confirmed.":"No eligible colleagues returned.");},"Finding colleagues…");}
  function handoverName(id){return handoverPeople.find(p=>p.membership_id===id)?.display_name||roster?.members?.find(p=>p.membership_id===id)?.display_name||"Staff "+id.slice(0,8);}
  function renderHandovers(){const root=el("handover-list");root.replaceChildren();if(!handoverRows.length)root.append(node("p","No handovers in the returned records."));for(const h of handoverRows){const card=node("article",undefined,"staff-record");card.append(node("h3",describe(h.state)),node("p",handoverName(h.sender_id)+" → "+handoverName(h.recipient_id),"staff-meta"),node("p",dateLabel(h.created_at),"staff-meta"),node("p",h.note));if(h.case_id)card.append(node("p","Linked request "+h.case_id.slice(0,8),"staff-meta"));if(h.decided_at)card.append(node("p","Recorded decision "+dateLabel(h.decided_at),"staff-meta"));if(h.state==="pending"){for(const action of ["acknowledge","cancel"]){const b=node("button",action==="acknowledge"?"Acknowledge handover":"Cancel handover","button secondary");b.type="button";b.addEventListener("click",async()=>{if(ctx.busy||!confirm(action==="acknowledge"?"Acknowledge receipt of this note? This does not transfer case ownership.":"Cancel this handover?"))return;const ok=await run(slug=>api.decideHandover(slug,h.id,action),d=>say("handover-result","Handover "+d.state+" by server."));if(ok)await loadHandovers();});card.append(b);}}root.append(card);}}
  async function loadHandovers(more=false){if(ctx.busy)return;const cursor=more?handoverCursor:null;if(more&&!cursor)return;const only=el("handover-pending").checked;await run(slug=>api.handovers(slug,cursor,only),data=>{const map=new Map((more?handoverRows:[]).map(h=>[h.id,h]));for(const h of data.handovers)map.set(h.id,h);handoverRows=[...map.values()];handoverCursor=data.next_cursor;renderHandovers();},"Refreshing handovers…");}
  el("handover-load").addEventListener("click",()=>loadHandovers());el("handover-more").addEventListener("click",()=>loadHandovers(true));el("handover-pending").addEventListener("change",()=>loadHandovers());el("handover-recipients").addEventListener("click",()=>loadHandoverPeople());el("handover-recipients-more").addEventListener("click",()=>loadHandoverPeople(true));
  el("handover-form").addEventListener("submit",async e=>{e.preventDefault();if(ctx.busy||!ctx.slug)return;if(!pendingHandover){const recipient_id=el("handover-recipient").value,case_id=el("handover-case").value||null,note=el("handover-note").value.trim();if(!WF_UUID.test(recipient_id)||note.length<4)return;if(!confirm("Send this handover note to the selected colleague?"))return;pendingHandover={recipient_id,case_id,note,request_key:crypto.randomUUID()};}const stamp=ctx.stamp();const ok=await run(slug=>api.createHandover(slug,pendingHandover),d=>{pendingHandover=null;el("handover-note").value="";el("handover-case").value="";say("handover-result","Handover "+d.state+" recorded. No external delivery or case transfer is implied.");},"Sending handover…");handoverControls();if(ok&&ctx.isCurrent(stamp))await loadHandovers();});
  el("handover-discard").addEventListener("click",()=>{if(!ctx.busy&&pendingHandover&&confirm("Discard local retry? This does not cancel a server record.")){pendingHandover=null;handoverControls();}});
  function renderTickets(){
    const root=el("v1-tickets");root.replaceChildren();if(!tickets){say("ticket-summary","No verified tickets loaded.");return;}
    const q=el("ticket-search").value.trim().toLowerCase();
    const filtered=tickets.filter(t=>(!el("ticket-filter").value||t.category===el("ticket-filter").value)&&(!el("ticket-status-filter").value||t.status===el("ticket-status-filter").value)&&(!q||[t.subject,t.description,t.id,t.category].some(v=>typeof v==="string"&&v.toLowerCase().includes(q))));
    say("ticket-summary",filtered.length+" of "+tickets.length+" returned tickets");
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
    try{const task=ctx.run(op);controls();const data=await task;if(!ctx.isCurrent(stamp)||!session.signedIn)return false;apply(data);if(el("staff-message").textContent===loading)say("staff-message","");return true;}
    catch(e){if(!ctx.isCurrent(stamp))return false;if(e.status===401){localExit("Session expired or rejected. Sign in again.");return false;}if(e.status===403){replyDrafts.clear();clearWorkforce();clearHandovers();commerce.clear();management.clear();native.clear();evidence.clear();documents.clear();aiStudio.clear();roster=null;rooms=null;renderSchedule();renderRooms();cases=null;tickets=null;settings=null;renderCases();renderTickets();el("settings-form").hidden=true;say("case-summary","Access must be verified again.");say("membership-result","");}say("staff-message",e.message);return false;}
    finally{controls();}
  }
  async function loadCases(){
    cases=null;renderCases();say("case-summary","No verified queue loaded.");return run(slug=>api.cases(slug),data=>{cases=data;renderCases();say("staff-message","Guest requests refreshed.");});
  }
  async function loadTickets(){
    tickets=null;renderTickets();return run(slug=>api.tickets(slug),data=>{tickets=data;renderTickets();say("staff-message","Department tickets loaded from server.");});
  }
  function iso(value){const d=new Date(value);if(!Number.isFinite(d.getTime()))throw staffError("Select a valid date and time.");return d.toISOString();}
  function dateLabel(value){const d=new Date(value);return Number.isFinite(d.getTime())?d.toLocaleString():String(value);}
  function renderStaffSelectors(){for(const id of ["profile-member","shift-member"]){const select=el(id),previous=select.value;select.replaceChildren(new Option("Choose staff member",""));for(const m of (roster?.members||[]).filter(x=>x.state==="active")){const name=m.display_name||m.employee_reference||("Staff member "+m.membership_id.slice(0,8));select.append(new Option(name+" · "+describe(m.role)+(m.display_name&&m.employee_reference?" · "+m.employee_reference:""),m.membership_id));}if([...select.options].some(o=>o.value===previous))select.value=previous;}}

  function workforceControls(locked=ctx.busy||authBusy){el("leave-fields").disabled=locked||!!pendingLeave;el("leave-send").textContent=pendingLeave?"Retry unchanged leave request":"Request leave";el("leave-discard").hidden=!pendingLeave;el("attendance-more").hidden=!attendanceCursor;el("leave-more").hidden=!leaveCursor;}
  function clearWorkforce(){attendanceRows=[];attendanceCursor=null;attendanceRange=null;leaveRows=[];leaveCursor=null;pendingLeave=null;el("attendance-list").replaceChildren();el("leave-list").replaceChildren();el("leave-form").reset();workforceControls();}
  function staffName(id){return roster?.members.find(m=>m.membership_id===id)?.display_name||"Staff "+id.slice(0,8);}
  function workforceButton(label,fn){const b=node("button",label,"button secondary");b.type="button";b.addEventListener("click",fn);return b;}
  function renderAttendance(){const root=el("attendance-list");root.replaceChildren();if(!attendanceRows.length)root.append(node("p","No scheduled shifts returned for this period."));for(const r of attendanceRows){const card=node("article",undefined,"staff-record");card.append(node("h3",staffName(r.membership_id)),node("p",dateLabel(r.starts_at)+" to "+dateLabel(r.ends_at)),node("p",r.checked_out_at?"Checked out":r.checked_in_at?"Checked in":"Not checked in","staff-meta"));if(r.checked_in_at)card.append(node("p","In: "+dateLabel(r.checked_in_at)));if(r.checked_out_at)card.append(node("p","Out: "+dateLabel(r.checked_out_at)));if(!r.checked_out_at){const action=r.checked_in_at?"check_out":"check_in";card.append(workforceButton(action==="check_in"?"Check in (own shift)":"Check out (own shift)",async()=>{if(ctx.busy||!confirm("Record attendance for your own shift?"))return;const ok=await run(slug=>api.attendanceAction(slug,r.shift_id,action),d=>say("staff-message","Attendance recorded at "+dateLabel(action==="check_in"?d.checked_in_at:d.checked_out_at)+"."));if(ok)await loadAttendance(false,true);}));}root.append(card);}}
  async function loadAttendance(more=false,keepRange=false){if(ctx.busy)return;if(!more&&!keepRange){try{attendanceRange={start:iso(el("schedule-start").value),end:iso(el("schedule-end").value)};}catch(e){say("staff-message",e.message);return;}attendanceRows=[];attendanceCursor=null;el("attendance-list").replaceChildren();}if(!attendanceRange)return;const cursor=more?attendanceCursor:null;if(more&&!cursor)return;await run(slug=>api.attendance(slug,attendanceRange.start,attendanceRange.end,cursor),d=>{const map=new Map((more?attendanceRows:[]).map(r=>[r.shift_id,r]));for(const r of d.attendance)map.set(r.shift_id,r);attendanceRows=[...map.values()];attendanceCursor=d.next_cursor;renderAttendance();},"Loading attendance…");}
  function renderLeave(){const root=el("leave-list");root.replaceChildren();if(!leaveRows.length)root.append(node("p","No leave requests returned."));const role=propertyRows.find(p=>p.slug===ctx.slug)?.role||cases?.staff_role;for(const r of leaveRows){const card=node("article",undefined,"staff-record");card.append(node("h3",staffName(r.membership_id)),node("p",describe(r.leave_kind)+" · "+describe(r.state),"staff-meta"),node("p",dateLabel(r.starts_at)+" to "+dateLabel(r.ends_at)));const actions=r.state==="requested"?["withdraw",...(!role||["owner","manager","hr"].includes(role)?["approve","decline"]:[])]:r.state==="approved"&&(!role||["owner","manager","hr"].includes(role))?["cancel"]:[];for(const action of actions){card.append(workforceButton(({withdraw:"Withdraw own request",approve:"Approve leave",decline:"Decline leave",cancel:"Cancel approved leave"})[action],async()=>{if(ctx.busy||!confirm("Confirm "+action+"? The server checks eligibility and overlapping shifts."))return;const ok=await run(slug=>api.decideLeave(slug,r.id,action),d=>say("staff-message","Leave "+d.state+" recorded."));if(ok)await loadLeave();}));}root.append(card);}}
  async function loadLeave(more=false){if(ctx.busy)return;const cursor=more?leaveCursor:null;if(more&&!cursor)return;await run(slug=>api.leaveRequests(slug,cursor),d=>{const map=new Map((more?leaveRows:[]).map(r=>[r.id,r]));for(const r of d.requests)map.set(r.id,r);leaveRows=[...map.values()];leaveCursor=d.next_cursor;renderLeave();},"Loading leave requests…");}
  el("attendance-load").addEventListener("click",()=>loadAttendance());el("attendance-more").addEventListener("click",()=>loadAttendance(true));el("leave-load").addEventListener("click",()=>loadLeave());el("leave-more").addEventListener("click",()=>loadLeave(true));
  el("leave-form").addEventListener("submit",async e=>{e.preventDefault();if(ctx.busy||!ctx.slug)return;if(!pendingLeave){try{const starts_at=iso(el("leave-start").value),ends_at=iso(el("leave-end").value);if(Date.parse(ends_at)<=Date.parse(starts_at)||Date.parse(ends_at)-Date.parse(starts_at)>93*86400000)throw Error("Choose a valid leave range up to 93 days.");if(!confirm("Submit your leave request?"))return;pendingLeave={starts_at,ends_at,leave_kind:el("leave-kind").value,request_key:crypto.randomUUID()};}catch(err){say("staff-message",err.message);return;}}const stamp=ctx.stamp(),ok=await run(slug=>api.requestLeave(slug,pendingLeave),d=>{pendingLeave=null;el("leave-form").reset();say("staff-message","Leave "+d.state+" recorded by server.");},"Recording leave request…");workforceControls();if(ok&&ctx.isCurrent(stamp))await loadLeave();});
  el("leave-discard").addEventListener("click",()=>{if(!ctx.busy&&pendingLeave&&confirm("Discard the local retry key? This does not cancel a server request.")){pendingLeave=null;workforceControls();}});
  function renderSchedule(){renderStaffSelectors();
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
  el("profile-member").addEventListener("change",()=>{const member=roster?.members.find(m=>m.membership_id===el("profile-member").value);el("profile-name").value=member?.display_name||"";el("profile-title").value=member?.job_title||"";el("profile-reference").value=member?.employee_reference||"";});
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
  el("case-search").addEventListener("input",renderCases);
  el("ticket-search").addEventListener("input",renderTickets);
  document.querySelectorAll("[data-view]").forEach(b=>b.addEventListener("click",()=>{if(!ctx.busy)showView(b.dataset.view);}));
  function selectProperty(slug){
    if(ctx.busy||authBusy||!session?.signedIn)return false;
    if(!/^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(slug)||slug.length>100)return false;
    if((pendingLeave||pendingHandover||pendingTicket||commerce.pending||management.pending||native.pending||evidence.pending||documents.pending||aiStudio.pending)&&!confirm("An unconfirmed operation may already exist. Switching property discards its local retry key. Continue?"))return false;
    ctx.select(slug);clearData();el("staff-slug").value=slug;
    const p=propertyRows.find(x=>x.slug===slug);
    say("workspace-title",p?p.display_name:"Staff workspace");
    say("property-label",p?p.display_name+" · "+describe(p.role)+" · "+p.time_zone:"Selected: "+slug+" · Access checked by each server request.");say("staff-message","");controls();return true;
  }
  function renderProperties(){
    const root=el("property-discovery-list");root.replaceChildren();
    for(const p of propertyRows){const card=node("article",undefined,"property-choice");const info=node("div");info.append(node("strong",p.display_name),node("p",describe(p.role)+" · "+p.time_zone+(p.membership_state==="invited"?" · Invitation pending":"")));const b=node("button",p.membership_state==="invited"?"Review invitation":"Open hotel","button secondary");b.type="button";b.addEventListener("click",()=>{if(!selectProperty(p.slug))return;if(p.membership_state==="invited"){showView("memberships");say("staff-message","Accept your invitation before accessing hotel records.");}else{showView(({owner:"management",manager:"management",reception:"cases",housekeeping:"rooms",maintenance:"tickets",kitchen:"dining",finance:"finance",hr:"schedule",procurement:"procurement",events:"events",it:"tickets"})[p.role]||"cases");}});card.append(info,b);root.append(card);}
    el("property-more").hidden=!propertyCursor;
    say("property-discovery-status",propertyRows.length?propertyRows.length+" linked hotel"+(propertyRows.length===1?"":"s")+(propertyCursor?" · More available":""):"No linked hotels returned. Ask your hotel administrator about an invitation.");
  }
  async function discoverProperties(more=false){
    if(ctx.busy||authBusy||!session?.signedIn)return;
    const stamp=ctx.stamp(),cursor=more?propertyCursor:null;if(more&&!cursor)return;
    if(!more)clearProperties();
    say("property-discovery-status","Finding your hotels…");
    authBusy=true;controls();
    try{const d=await api.properties(cursor);if(!ctx.isCurrent(stamp)||!session?.signedIn)return;
      const map=new Map(propertyRows.map(p=>[p.slug,p]));for(const p of d.properties)map.set(p.slug,p);propertyRows=[...map.values()];propertyCursor=d.next_cursor;renderProperties();
    }catch(e){if(ctx.isCurrent(stamp)){if(e.status===401)localExit("Session expired. Sign in again.");else say("property-discovery-status",e.message+" You can still enter a known hotel code.");}}
    finally{authBusy=false;controls();}
  }
  el("property-discover").addEventListener("click",()=>discoverProperties());el("property-more").addEventListener("click",()=>discoverProperties(true));
  el("property-form").addEventListener("submit",e=>{e.preventDefault();selectProperty(el("staff-slug").value.trim());});
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
    await run(slug=>api.membership(slug,action,subject,role),d=>{say("membership-result","Membership "+d.membership_id+" · "+d.role+" · "+d.state);say("staff-message","Membership command confirmed. No account or email delivery is implied.");if(action==="revoke"){replyDrafts.clear();clearWorkforce();clearHandovers();commerce.clear();management.clear();native.clear();evidence.clear();documents.clear();aiStudio.clear();roster=null;rooms=null;renderSchedule();renderRooms();cases=null;tickets=null;settings=null;renderCases();renderTickets();el("settings-form").hidden=true;}});
  }
  el("membership-form").addEventListener("submit",e=>{e.preventDefault();membership("invite");});el("accept-membership").addEventListener("click",()=>membership("accept"));el("revoke-membership").addEventListener("click",()=>membership("revoke"));
  el("login-form").addEventListener("submit",async e=>{
    e.preventDefault();if(authBusy||!session)return;authBusy=true;controls();say("login-status","Signing in…");const password=el("password").value;el("password").value="";
    try{await session.signIn(el("email").value.trim(),password);el("login-panel").hidden=true;el("staff-workspace").hidden=false;el("signout").hidden=false;showView("cases");expiryTimer=setTimeout(()=>localExit("Session expired. Sign in again."),Math.max(0,session.expiresAt-Date.now()));el("staff-slug").focus();}
    catch(e){say("login-status",e.message);}finally{authBusy=false;controls();}
  });
  el("signout").addEventListener("click",async()=>{if(authBusy)return;if((pendingLeave||pendingHandover||pendingTicket||commerce.pending||management.pending||native.pending||evidence.pending||documents.pending||aiStudio.pending)&&!confirm("A ticket, dining order, stock operation, room hold, provider command or document upload is unconfirmed. Signing out discards its local retry key, not the server record. Continue?"))return;authBusy=true;const task=session.signOut();localExit("Signed out of this workspace.");const revoked=await task;authBusy=false;controls();if(!revoked)say("login-status","Signed out locally. Provider session revocation could not be confirmed.");});
  window.addEventListener("pagehide",()=>{clearProperties();clearTimeout(expiryTimer);session?.clear();ctx.select("");clearData();});
  window.addEventListener("pageshow",e=>{if(e.persisted)localExit("Sign in again to access staff records.");});
  (async()=>{try{const r=await fetch(new URL("./staff-auth-config.json",location.href),{cache:"no-store",credentials:"same-origin",redirect:"error"});if(!r.ok)throw staffError("Staff identity configuration unavailable.");session=staffSession(window.fetch.bind(window),await r.json());api=staffApi(window.fetch.bind(window),session);say("login-status","Sign in with your confirmed hotel identity.");}catch{say("login-status","Staff sign-in is unavailable until an authorized identity provider is configured.");}finally{controls();}})();
})();
