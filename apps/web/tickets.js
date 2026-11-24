"use strict";
const $=(id)=>document.getElementById(id);
const make=(tag,text,cls)=>{const node=document.createElement(tag);if(text!==undefined)node.textContent=text;if(cls)node.className=cls;return node;};
const base=()=>"/api/properties/"+encodeURIComponent($("property").value)+"/staff/tickets";
const show=(id,message)=>{$(id).textContent=message;};
let pendingCreate=null;
let contextRevision=0;
let creating=false;
function resetWorkspace(note){
  contextRevision+=1;
  pendingCreate=null;
  $("ticket-list").replaceChildren();
  $("metrics").replaceChildren();
  show("connection-status",note);
  show("form-status","No ticket submitted in the selected property context.");
}
function stableCreateRequest(draft){
  // The same unchanged form retains its idempotency key across network retries.
  // Clear it after a confirmed success so later entries create distinct tickets.
  const snapshot=JSON.stringify({property:$("property").value,...draft});
  if(!pendingCreate || pendingCreate.snapshot!==snapshot){
    pendingCreate={snapshot,key:secureId()};
  }
  return {...draft,request_key:pendingCreate.key};
}
async function api(path,method="GET",payload,key=$("staff-key").value){
  if(!key)throw Error("Enter your development staff key first.");
  const headers={"X-Staff-Key":key};
  if(payload)headers["Content-Type"]="application/json";
  const response=await fetch(path,{method,headers,body:payload?JSON.stringify(payload):undefined,cache:"no-store"});
  const body=await response.json();
  if(!response.ok)throw Error(typeof body.detail==="string"?body.detail:"Request failed ("+response.status+")");
  return body;
}
function secureId(){
  if(!globalThis.crypto?.randomUUID)throw Error("Secure browser random UUID unavailable. Use localhost or HTTPS.");
  return crypto.randomUUID().replaceAll("-","");
}
function button(label,fn){const el=make("button",label,"button secondary");el.type="button";el.style.marginRight="7px";el.style.marginTop="10px";el.addEventListener("click",fn);return el;}
function formatDate(value){const d=new Date(value);return Number.isNaN(d.valueOf())?"Time unavailable":d.toLocaleString();}
async function refresh(){
  const revision=contextRevision;
  const selectedKey=$("staff-key").value;
  const selectedBase=base();
  const root=$("ticket-list");root.replaceChildren();
  show("connection-status","Loading this property\u0027s local tickets...");
  try{
    const status=$("status-filter").value, category=$("category-filter").value;
    const query=new URLSearchParams();
    if(status)query.set("status",status);
    if(category)query.set("category",category);
    const [metrics,tickets]=await Promise.all([api(selectedBase+"/metrics","GET",undefined,selectedKey),api(selectedBase+(query.size?"?"+query.toString():""),"GET",undefined,selectedKey)]);
    if(revision!==contextRevision)return; // Ignore responses after hotel or key changes.
    $("metrics").replaceChildren();
    for(const [key,value] of [
      ["Total tickets",metrics.total],["Unresolved",metrics.unresolved],
      ["Overdue",metrics.overdue],["Resolved",metrics.by_status.resolved]
    ]){
      const card=make("div",key+": "+value,"notice");card.style.marginBottom="10px";$("metrics").append(card);
    }
    show("connection-status","Connected to "+$("property").value+" development ticket queue. No live notifications.");
    if(!tickets.tickets.length){root.append(make("p","No tickets match the selected filters."));return;}
    for(const ticket of tickets.tickets){
      const article=make("article",undefined,"panel");article.style.marginTop="13px";
      article.append(make("h3",ticket.subject));
      article.append(make("p",ticket.category.toUpperCase()+" · "+ticket.priority.toUpperCase()+" · "+ticket.status.toUpperCase()+(ticket.overdue?" · OVERDUE":"")));
      article.append(make("p",ticket.description));
      article.append(make("p","Due: "+formatDate(ticket.due_at)+" · Assigned: "+(ticket.assigned_to||"Nobody yet")));
      const actions=make("div");
      if(["open","reopened"].includes(ticket.status))actions.append(button("Claim",()=>act(ticket.id,"claim")));
      if(ticket.status==="assigned")actions.append(button("Start work",()=>act(ticket.id,"start")));
      const notes=make("textarea");notes.rows=2;notes.maxLength=1200;notes.placeholder="Internal note or resolution (no confidential guest information)";notes.setAttribute("aria-label","Internal ticket note");
      article.append(notes);
      actions.append(button("Add internal note",()=>{
        if(notes.value.trim().length<4)return show("connection-status","Write at least four characters.");
        return act(ticket.id,"notes",{text:notes.value.trim()});
      }));
      if(ticket.status==="in_progress")actions.append(button("Resolve",()=>{
        if(notes.value.trim().length<8)return show("connection-status","Resolution requires at least eight characters.");
        return act(ticket.id,"resolve",{summary:notes.value.trim()});
      }));
      if(ticket.status==="resolved")actions.append(button("Reopen",()=>{
        if(notes.value.trim().length<4)return show("connection-status","Explain why the ticket must reopen.");
        return act(ticket.id,"reopen",{text:notes.value.trim()});
      }));
      const history=make("div");history.hidden=true;history.className="notice";
      actions.append(button("View history",async()=>{
        try{const detail=await api(base()+"/"+encodeURIComponent(ticket.id));history.replaceChildren();
          for(const h of detail.history){history.append(make("p",formatDate(h.created_at)+" · "+h.event+(h.details?": "+h.details:"")));}
          history.hidden=false;
        }catch(e){show("connection-status",e.message);}
      }));
      article.append(actions,history);root.append(article);
    }
  }catch(e){if(revision!==contextRevision)return;show("connection-status","Unable to load tickets: "+e.message);root.append(make("p","Access denied or ticket service unavailable."));}
}
async function act(id,verb,body){
  const revision=contextRevision, selectedBase=base(), selectedKey=$("staff-key").value;
  try{
    await api(selectedBase+"/"+encodeURIComponent(id)+"/"+verb,"POST",body,selectedKey);
    if(revision!==contextRevision)return;
    show("connection-status","Ticket "+verb+" recorded locally; no outbound message sent.");
    await refresh();
  }catch(e){if(revision===contextRevision)show("connection-status","Could not update ticket: "+e.message);}
}
$("ticket-form").addEventListener("submit",async(event)=>{
  event.preventDefault();if(creating || !event.currentTarget.reportValidity())return;
  creating=true;
  const revision=contextRevision, selectedBase=base(), selectedKey=$("staff-key").value;
  const btn=$("create");btn.disabled=true;
  try{
    const payload=stableCreateRequest({
      category:$("category").value,priority:$("priority").value,
      subject:$("subject").value.trim(),description:$("description").value.trim(),
      origin_case_id:$("source-case").value.trim()||null
    });
    const result=await api(selectedBase,"POST",payload,selectedKey);
    if(revision!==contextRevision)return;
    pendingCreate=null;
    show("form-status","Ticket "+result.ticket_id+" created as "+result.status+". Not assigned yet.");
    $("subject").value="";$("description").value="";$("source-case").value="";
    await refresh();
  }catch(e){if(revision===contextRevision)show("form-status","Ticket creation failed: "+e.message);}
  finally{creating=false;btn.disabled=false;}
});
$("refresh").addEventListener("click",refresh);
$("apply-filter").addEventListener("click",refresh);
$("property").addEventListener("change",()=>resetWorkspace("Hotel changed. Load this property's queue with its correct key."));
$("staff-key").addEventListener("input",()=>resetWorkspace("Development staff key changed. Refresh to verify access."));
