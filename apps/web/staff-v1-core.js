"use strict";
const WF_UUID=/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const WF_ROLES=["manager","reception","housekeeping","maintenance","kitchen","finance"];
const WF_CASE_STATES=["queued","claimed","responded"];
const WF_TICKET_STATES=["open","assigned","in_progress","resolved","reopened"];
const WF_CATEGORIES=["it","reception","housekeeping","maintenance","kitchen","billing","general"];
function staffError(message,status=0){return Object.assign(new Error(message),{status});}
function staffConfig(raw){
  if(!raw||raw.enabled!==true||raw.provider!=="supabase"||typeof raw.url!=="string"||!/^https:\/\/[a-z0-9]{20}\.supabase\.co$/.test(raw.url)||typeof raw.publishableKey!=="string"||!/^sb_publishable_[A-Za-z0-9_-]+$/.test(raw.publishableKey))throw staffError("Staff identity provider is not configured.");
  return {url:raw.url,publishableKey:raw.publishableKey};
}
function staffSession(fetcher,raw,clock=Date.now){
  const config=staffConfig(raw);let session=null,epoch=0;
  const alive=()=>session&&clock()<session.expiresAt;
  return {
    get signedIn(){return !!alive();},
    get expiresAt(){return session?.expiresAt||0;},
    token(){if(!alive()){session=null;throw staffError("Session expired. Sign in again.",401);}return session.token;},
    async signIn(email,password){
      const generation=++epoch;session=null;
      let res;try{res=await fetcher(config.url+"/auth/v1/token?grant_type=password",{method:"POST",headers:{apikey:config.publishableKey,"Content-Type":"application/json"},body:JSON.stringify({email,password}),cache:"no-store",credentials:"omit",redirect:"error"});}catch{throw staffError("Identity service unavailable.");}
      if(!res.ok)throw staffError("Sign-in rejected or identity service unavailable.",res.status);
      const data=await res.json();
      if(generation!==epoch)throw staffError("Sign-in cancelled.");
      if(typeof data.access_token!=="string"||! /^[A-Za-z0-9_.-]{1,8192}$/.test(data.access_token)||!Number.isFinite(data.expires_in)||data.expires_in<=0||data.user?.role!=="authenticated"||data.user?.is_anonymous!==false||!(data.user?.email_confirmed_at||data.user?.phone_confirmed_at))throw staffError("Verified permanent identity required.");
      session={token:data.access_token,expiresAt:clock()+Math.min(data.expires_in,86400)*1000};
      // Refresh token is deliberately not retained. Reauthentication is explicit.
    },
    async signOut(){
      const old=session;++epoch;session=null;
      if(!old)return true;
      try{const res=await fetcher(config.url+"/auth/v1/logout?scope=local",{method:"POST",headers:{apikey:config.publishableKey,Authorization:"Bearer "+old.token},cache:"no-store",credentials:"omit",redirect:"error"});return res.ok||[401,403,404].includes(res.status);}catch{return false;}
    },
    clear(){++epoch;session=null;}
  };
}
function staffApi(fetcher,session){
  function base(slug){if(typeof slug!=="string"||slug.length>100||! /^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(slug))throw staffError("Enter a valid hotel code.");return "/api/v1/properties/"+encodeURIComponent(slug)+"/staff";}
  function id(value){if(typeof value!=="string"||!WF_UUID.test(value))throw staffError("Invalid record identifier.");return value;}
  async function call(slug,path,method="GET",body){
    const token=session.token(),headers={Authorization:"Bearer "+token,Accept:"application/json"};
    if(body!==undefined)headers["Content-Type"]="application/json";
    let response;try{response=await fetcher(base(slug)+path,{method,headers,...(body===undefined?{}:{body:JSON.stringify(body)}),cache:"no-store",credentials:"same-origin",redirect:"error"});}catch(e){throw staffError("Connection unavailable or action outcome unconfirmed.");}
    if(!response.ok)throw staffError(({401:"Session rejected. Sign in again.",403:"Your account is not authorized for this action.",404:"Record or service unavailable.",409:"State changed or request conflicts. Reload before retrying.",422:"The service rejected the submitted fields.",429:"Too many requests. Try again later.",503:"Service unavailable."})[response.status]||"The service could not confirm the action.",response.status);
    try{return await response.json();}catch{throw staffError("Unreadable service response.");}
  }
  function valid(condition){if(!condition)throw staffError("Unexpected service response. Reload to verify the outcome.");}
  return {
    async cases(slug){const d=await call(slug,"/cases");valid(d?.property===slug&&WF_ROLES.includes(d.staff_role)&&Array.isArray(d.cases)&&d.cases.length<=100&&d.cases.every(c=>WF_UUID.test(c.id)&&WF_CASE_STATES.includes(c.status)));return d;},
    async caseAction(slug,caseId,action,message){if(!["claim","respond"].includes(action))throw staffError("Unsupported case action.");if(action==="respond"&&(typeof message!=="string"||message.length<2||message.length>3000))throw staffError("Enter a valid reply.");const d=await call(slug,"/cases/"+id(caseId)+"/"+action,"POST",action==="respond"?{message}:undefined);valid(d?.property===slug&&d.case_id===caseId&&d.status===(action==="claim"?"claimed":"responded"));return d;},
    async tickets(slug){const d=await call(slug,"/tickets");valid(Array.isArray(d?.tickets)&&d.tickets.length<=100&&d.tickets.every(t=>WF_UUID.test(t.id)&&WF_TICKET_STATES.includes(t.status)&&WF_CATEGORIES.includes(t.category)));return d.tickets;},
    async createTicket(slug,body){const d=await call(slug,"/tickets","POST",body);valid(WF_UUID.test(d?.ticket_id)&&WF_TICKET_STATES.includes(d.status));return d;},
    async ticketAction(slug,ticketId,action,note){if(!["claim","start","resolve","reopen","note"].includes(action))throw staffError("Unsupported ticket action.");const d=await call(slug,"/tickets/"+id(ticketId)+"/transition","POST",{action,...(note?{note}:{})});valid(d?.ticket_id===ticketId&&WF_TICKET_STATES.includes(d.status));return d;},
    async membership(slug,action,subject,role){if(!["invite","accept","revoke"].includes(action))throw staffError("Unsupported membership action.");if(action!=="accept"&&(typeof subject!=="string"||subject.length<8||subject.length>255))throw staffError("Enter the verified provider identity.");if(action==="invite"&&!WF_ROLES.includes(role))throw staffError("Select an allowed role.");const d=await call(slug,"/memberships/"+action,"POST",action==="accept"?undefined:{provider_subject:subject,...(action==="invite"?{role}:{})});valid(WF_UUID.test(d?.membership_id)&&typeof d.state==="string"&&WF_ROLES.includes(d.role));return d;},
    async settings(slug){const d=await call(slug,"/settings");valid(typeof d?.guest_enquiries_enabled==="boolean"&&typeof d.ai_enabled==="boolean"&&Number.isInteger(d.revision)&&d.revision>=1);return d;},
    async updateSettings(slug,revision,enabled){if(!Number.isInteger(revision)||revision<1||typeof enabled!=="boolean")throw staffError("Load current settings first.");const d=await call(slug,"/settings","PUT",{revision,guest_enquiries_enabled:enabled});valid(typeof d?.guest_enquiries_enabled==="boolean"&&typeof d.ai_enabled==="boolean"&&Number.isInteger(d.revision)&&d.revision>=revision);return d;}
  };
}
function staffContext(){
  let slug="",generation=0,busy=false;
  return {
    get slug(){return slug;},get busy(){return busy;},
    select(value){slug=value;++generation;busy=false;},
    async run(operation){if(busy)throw staffError("Another operation is pending.");const current=slug,version=generation;busy=true;try{const value=await operation(current);if(version!==generation)throw staffError("Property or session changed.");return value;}catch(e){if(version!==generation)throw staffError("Property or session changed.");throw e;}finally{if(version===generation)busy=false;}},
    stamp(){return generation;},isCurrent(value){return generation===value;}
  };
}
if(typeof module!=="undefined"&&module.exports)module.exports={staffConfig,staffSession,staffApi,staffContext};
