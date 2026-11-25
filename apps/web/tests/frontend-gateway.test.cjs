"use strict";
const {test}=require("node:test");
const assert=require("node:assert/strict");
const http=require("node:http");
const {once}=require("node:events");
const {config,handler}=require("../../frontend/server.cjs");
const env={WF_FRONTEND_API_ORIGIN:"https://backend.example.invalid"};
test("frontend configuration requires HTTPS and publishable identity credentials",()=>{
 assert.throws(()=>config({WF_FRONTEND_API_ORIGIN:"http://backend.example.invalid"}));
 assert.throws(()=>config({WF_FRONTEND_API_ORIGIN:"https://backend.example.invalid/private"}));
 assert.throws(()=>config({...env,WF_FRONTEND_AUTH_ENABLED:"1",WF_SUPABASE_URL:"https://abcdefghijklmnopqrst.supabase.co",WF_SUPABASE_PUBLISHABLE_KEY:"sb_secret_test"}));
 assert.equal(config(env).identity.enabled,false);
});
test("real HTTP gateway serves only approved assets, forwards approved versioned API and denies legacy paths",async()=>{
 const seen=[];
 const upstream=http.createServer((req,res)=>{
  seen.push({url:req.url,headers:req.headers,method:req.method});
  if(req.url.includes("redirect-test")){res.writeHead(302,{Location:"https://example.invalid/"});res.end();return;}
  if(req.url.includes("html-test")){res.writeHead(200,{"Content-Type":"text/html"});res.end("<html>unsafe</html>");return;}
  res.writeHead(200,{"Content-Type":"application/json","Set-Cookie":"private=untrusted"});res.end(JSON.stringify({ok:true}));
 });
 upstream.listen(0,"127.0.0.1");await once(upstream,"listening");
 const gateway=http.createServer(handler({upstream:"http://127.0.0.1:"+upstream.address().port,identity:{enabled:false,provider:"supabase"}}));
 gateway.listen(0,"127.0.0.1");await once(gateway,"listening");
 const base="http://127.0.0.1:"+gateway.address().port;
 try{
  const home=await fetch(base+"/");assert.equal(home.status,200);assert.match(await home.text(),/guest-v1-core.js/);
  const staff=await fetch(base+"/staff");assert.equal(staff.status,200);assert.match(await staff.text(),/staff-v1-core.js/);assert.match(staff.headers.get("content-security-policy"),/frame-ancestors 'none'/);
  const auth=await fetch(base+"/staff-auth-config.json");assert.equal((await auth.json()).enabled,false);
  for(const url of ["/static/index.html","/static/app.js","/static/tests/staff-v1.test.cjs","/api/properties/demo-hotel/staff/enquiries","/api/v1/properties/hotel-a/staff/payments","/static/%2e%2e%2fserver.cjs"])assert.equal((await fetch(base+url)).status,404);
  assert.equal(seen.length,0);
  const req=await fetch(base+"/api/v1/properties/hotel-a/staff/cases",{headers:{Authorization:"Bearer synthetic.token",Cookie:"private=fixture","X-Staff-Key":"legacy","X-Forwarded-For":"192.0.2.1"}});
  assert.equal(req.status,200);assert.equal(req.headers.get("set-cookie"),null);assert.equal(req.headers.get("cache-control"),"no-store");assert.equal(seen[0].headers.authorization,"Bearer synthetic.token");assert.equal(seen[0].headers.cookie,undefined);assert.equal(seen[0].headers["x-staff-key"],undefined);assert.equal(seen[0].headers["x-forwarded-for"],undefined);
  assert.equal((await fetch(base+"/api/v1/properties/redirect-test/staff/cases")).status,502);
  assert.equal((await fetch(base+"/api/v1/properties/html-test/staff/cases")).status,502);
  assert.equal((await fetch(base+"/api/v1/properties/hotel-a/staff/settings",{method:"PUT",headers:{"Content-Type":"text/html"},body:"test"})).status,415);
 }finally{gateway.closeAllConnections();upstream.closeAllConnections();await Promise.all([new Promise(r=>gateway.close(r)),new Promise(r=>upstream.close(r))]);}
});

test("document gateway is disabled by default; enabled routes accept only authenticated bounded binary attachments",async()=>{
 const seen=[];const id="12345678-1234-1234-1234-123456789abc",bytes=Buffer.from([0,1,2,255]);
 const upstream=http.createServer(async(req,res)=>{const parts=[];for await(const chunk of req)parts.push(chunk);seen.push({url:req.url,headers:req.headers,body:Buffer.concat(parts)});if(req.method==="POST"){res.writeHead(201,{"Content-Type":"application/json"});res.end(JSON.stringify({document_id:id,size:4}));}else if(req.url.includes("html-test")){res.writeHead(200,{"Content-Type":"text/html","Content-Disposition":"inline"});res.end("<script>unsafe</script>");}else{res.writeHead(200,{"Content-Type":"application/octet-stream","Content-Disposition":"attachment; filename=untrusted.html","Set-Cookie":"untrusted=1"});res.end(bytes);}});
 upstream.listen(0,"127.0.0.1");await once(upstream,"listening");
 const settings={upstream:"http://127.0.0.1:"+upstream.address().port,identity:{enabled:false}};
 const enabled=http.createServer(handler({...settings,documentsEnabled:true})),disabled=http.createServer(handler(settings));
 for(const server of [enabled,disabled]){server.listen(0,"127.0.0.1");await once(server,"listening");}
 const base="http://127.0.0.1:"+enabled.address().port,off="http://127.0.0.1:"+disabled.address().port,route="/api/v1/properties/hotel-a/staff/documents";
 const headers={Authorization:"Bearer fixture.token","Content-Type":"application/octet-stream"};
 try{
  assert.equal((await fetch(off+route+"/"+id,{headers})).status,503);
  assert.equal((await fetch(base+route+"/"+id)).status,401);
  assert.equal((await fetch(base+route,{method:"POST",headers:{...headers,"Content-Type":"text/html"},body:"bad"})).status,415);
  assert.equal((await fetch(base+route,{method:"POST",headers,body:Buffer.alloc(2000001)})).status,413);
  assert.equal(seen.length,0);
  const upload=await fetch(base+route,{method:"POST",headers,body:bytes});assert.equal(upload.status,201);assert.deepEqual(seen[0].body,bytes);
  const download=await fetch(base+route+"/"+id,{headers});assert.equal(download.status,200);assert.deepEqual(Buffer.from(await download.arrayBuffer()),bytes);assert.equal(download.headers.get("content-disposition"),'attachment; filename="private-document.bin"');assert.equal(download.headers.get("set-cookie"),null);assert.equal(download.headers.get("cache-control"),"no-store");
  assert.equal((await fetch(base+"/api/v1/properties/html-test/staff/documents/"+id,{headers})).status,502);
 }finally{for(const server of [enabled,disabled,upstream])server.closeAllConnections();await Promise.all([enabled,disabled,upstream].map(server=>new Promise(r=>server.close(r))));}
});
