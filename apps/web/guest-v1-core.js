"use strict";
function guestApi(fetcher) {
  const slugPattern=/^[a-z0-9][a-z0-9-]{0,98}[a-z0-9]$|^[a-z0-9]$/;
  const uuid=/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
  const proof=/^[A-Za-z0-9_-]{32,128}$/;
  const states=new Set(["queued","claimed","responded"]);
  const endpoint=slug=>{if(!slugPattern.test(slug))throw Error("Enter a valid hotel code.");return "/api/v1/properties/"+encodeURIComponent(slug)+"/enquiries";};
  async function request(url,options){
    let response;
    try{response=await fetcher(url,{cache:"no-store",credentials:"same-origin",redirect:"error",...options});}
    catch{throw Error("Connection interrupted. The outcome is not confirmed.");}
    if(!response.ok){
      const messages={404:"Hotel or receipt unavailable.",409:"Request conflict. Do not create another request until this is checked.",422:"The request was rejected. Check the fields.",429:"Too many requests. Try again later.",503:"Hotel service is temporarily unavailable."};
      throw Error(messages[response.status]||"The service could not confirm this request.");
    }
    let data;try{data=await response.json()}catch{throw Error("The service returned an unreadable response.");}
    if(!data||typeof data.case_id!=="string"||!uuid.test(data.case_id)||!states.has(data.status))throw Error("The service returned an unexpected request state.");
    return data;
  }
  return {
    async submit(slug,body){
      if(!proof.test(body.receipt_token)||!/^[A-Za-z0-9_-]{8,100}$/.test(body.request_key))throw Error("Invalid request proof.");
      const result=await request(endpoint(slug),{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});
      if(result.receipt_token!==body.receipt_token)throw Error("Receipt could not be verified.");
      return result;
    },
    async status(slug,id,token){
      if(!uuid.test(id)||!proof.test(token))throw Error("Check your case ID and private receipt token.");
      const result=await request(endpoint(slug)+"/"+encodeURIComponent(id),{method:"GET",headers:{"X-Receipt-Token":token}});
      if(result.case_id.toLowerCase()!==id.toLowerCase())throw Error("Receipt could not be verified.");
      return result;
    }
  };
}
function createGuestJourney(api,randomHex){
  let pending=null,active=null,busy=false,epoch=0;
  function snapshot(slug,fields){return JSON.stringify([slug,fields.kind,fields.name,fields.contact,fields.details]);}
  return {
    get pending(){return pending!==null;},
    get busy(){return busy;},
    get active(){return active?{...active}:null;},
    async submit(slug,fields){
      if(busy)throw Error("A request is already being checked.");
      if(active)throw Error("Save your current receipt and start a new request first.");
      const key=snapshot(slug,fields);
      if(pending&&pending.key!==key)throw Error("Retry the original details first, or explicitly discard the unconfirmed request.");
      if(!pending)pending={key,slug,body:{kind:fields.kind,name:fields.name,contact:fields.contact,details:fields.details,request_key:randomHex(16),receipt_token:randomHex(32)}};
      busy=true;const generation=++epoch;
      try{
        const result=await api.submit(pending.slug,pending.body);
        if(generation!==epoch)throw Error("Request context changed.");
        active={slug,case_id:result.case_id,token:pending.body.receipt_token};
        pending=null;
        return result;
      }finally{busy=false;}
    },
    async recover(slug,id,token){
      if(busy||pending)throw Error("Resolve the pending submission before checking another receipt.");
      busy=true;const generation=++epoch;
      try{
        const result=await api.status(slug,id,token);
        if(generation!==epoch)throw Error("Request context changed.");
        active={slug,case_id:result.case_id,token};
        return result;
      }finally{busy=false;}
    },
    async refresh(){
      if(!active)throw Error("Recover a receipt first.");
      return this.recover(active.slug,active.case_id,active.token);
    },
    reset(){
      if(busy)throw Error("Wait for the current request to finish.");
      ++epoch;pending=null;active=null;
    }
  };
}
if(typeof module!=="undefined"&&module.exports)module.exports={guestApi,createGuestJourney};
