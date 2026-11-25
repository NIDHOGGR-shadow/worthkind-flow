"use strict";
const {test}=require("node:test");
const assert=require("node:assert/strict");
const {commerceApi}=require("../commerce-core.js");
const id="12345678-1234-1234-1234-123456789abc", other="22345678-1234-1234-1234-123456789abc";
const proof="a".repeat(64),guest={slug:"hotel-a",case_id:id,token:proof};
const ok=data=>({ok:true,json:async()=>data});
const identity={token:()=>"staff.fixture.token"};
const stay={request_key:"reservation-key",room_type_id:null,arrival:"2026-12-01",departure:"2026-12-03",adults:2,children:0,room_count:1};
test("public discovery never transmits receipt or staff token",async()=>{
 const calls=[];const api=commerceApi(async(url,options)=>{calls.push([url,options]);return ok(url.endsWith("/content")?{content:[{key:"hotel",content:{title:"Hotel",body:"Published information"}}]}:url.endsWith("/rooms")?{rooms:[{id,name:"Room",max_guests:2}]}:url.endsWith("/menu")?{items:[{id,name:"Meal",price_minor:250000,currency:"NGN"}]}:{venues:[{id,name:"Hall",capacity:50}]});},identity);
 const d=await api.catalog("hotel-a");assert.equal(d.rooms.length,1);assert.equal(d.menu.length,1);
 assert.equal(calls.length,4);assert.ok(calls.every(([,o])=>!o.headers.Authorization&&!o.headers["X-Receipt-Token"]&&o.cache==="no-store"));
});
test("receipt-scoped reservation requests require nonbinding server flags",async()=>{
 const calls=[];const api=commerceApi(async(url,options)=>{calls.push([url,options]);return ok({id,state:"requested",booking_confirmed:false,inventory_held:false});},identity);
 await api.requestStay(guest,stay);assert.equal(calls[0][0],"/api/v1/properties/hotel-a/guest/cases/"+id+"/reservation-intents");assert.equal(calls[0][1].headers["X-Receipt-Token"],proof);assert.equal(calls[0][1].headers.Authorization,undefined);assert.deepEqual(JSON.parse(calls[0][1].body),stay);
 await assert.rejects(api.requestStay(guest,{...stay,departure:stay.arrival}));await assert.rejects(api.requestStay({...guest,token:"short"},stay));assert.equal(calls.length,1);
 await assert.rejects(commerceApi(async()=>ok({id,state:"requested",booking_confirmed:true,inventory_held:false})).requestStay(guest,stay));
});
test("reservation queue and withdrawal bind exact record and do not confirm bookings",async()=>{
 const api=commerceApi(async(url)=>ok(url.endsWith("/withdraw")?{id,state:"withdrawn",booking_confirmed:false}:url.endsWith("/review")?{id,state:"under_review",booking_confirmed:false}:{intents:[{id,state:"requested"}],booking_confirmed:false,inventory_held:false}),identity);
 assert.equal((await api.intents(guest))[0].id,id);await api.withdraw(guest,id);await api.reviewStay("hotel-a",id,"review");await assert.rejects(api.withdraw(guest,other));
});
test("venue request requires valid range and private receipt",async()=>{
 const calls=[];const api=commerceApi(async(url,options)=>{calls.push([url,options]);return ok({id,state:"requested"});});
 const b={venue_id:other,request_key:"venue-key",starts_at:"2026-12-01T10:00:00Z",ends_at:"2026-12-01T14:00:00Z",attendance:40};
 await api.requestVenue(guest,b);assert.equal(calls[0][1].headers["X-Receipt-Token"],proof);await assert.rejects(api.requestVenue(guest,{...b,attendance:0}));assert.equal(calls.length,1);
});
test("dining submission rejects duplicate lines and verifies server order totals",async()=>{
 const calls=[];const api=commerceApi(async(url,options)=>{calls.push([url,options]);return ok({id,state:"submitted",total_minor:500000,currency:"NGN",payment_confirmed:false});},identity);
 const b={request_key:"order-key",room_id:null,lines:[{item_id:id,quantity:2}]};assert.equal((await api.createOrder("hotel-a",b)).total_minor,500000);
 assert.equal(calls[0][1].headers.Authorization,"Bearer staff.fixture.token");await assert.rejects(api.createOrder("hotel-a",{...b,lines:[...b.lines,...b.lines]}));assert.equal(calls.length,1);
});
test("staff transitions and financial reconciliation never fabricate live verification",async()=>{
 const api=commerceApi(async(url)=>ok(url.endsWith("/transition")?{id,state:"ready",payment_confirmed:false}:{id,state:"verified",mode:"test",payment_confirmed:false}),identity);
 await api.diningAction("hotel-a",id,"ready");assert.equal((await api.verify("hotel-a",id)).payment_confirmed,false);
 await assert.rejects(commerceApi(async()=>ok({id,state:"verified",mode:"test",payment_confirmed:true}),identity).verify("hotel-a",id));
});
test("checkout accepts only exact HTTPS Paystack origin and pending links",async()=>{
 const d={id,reference:"wf-"+id,state:"pending",mode:"test",payment_confirmed:false,checkout_url:"https://checkout.paystack.com/test"};
 assert.equal((await commerceApi(async()=>ok(d),identity).checkout("hotel-a",id,"guest@example.invalid")).checkout_url,d.checkout_url);
 for(const url of ["https://checkout.paystack.com.evil.invalid/x","http://checkout.paystack.com/x","https://user@checkout.paystack.com/x","javascript:alert(1)"]){await assert.rejects(commerceApi(async()=>ok({...d,checkout_url:url}),identity).checkout("hotel-a",id,"guest@example.invalid"));}
 await assert.rejects(commerceApi(async()=>ok({...d,state:"verified"}),identity).checkout("hotel-a",id,"guest@example.invalid"));
});
test("PMS availability does not represent a hold or binding quote",async()=>{
 const d={provider:"cloudbeds",inventory_held:false,rates_binding:false,retrieved_at:"2026-11-25T20:00:00Z",room_types:[{room_type_id:"A",rooms_available:3}]};
 const b={start:"2026-12-01",end:"2026-12-03",adults:2,children:0,rooms:1};
 assert.equal((await commerceApi(async()=>ok(d),identity).availability("hotel-a",b)).rooms[0].rooms_available,3);
 await assert.rejects(commerceApi(async()=>ok({...d,inventory_held:true}),identity).availability("hotel-a",b));
});
test("refund request and dual approval send only authorized API commands",async()=>{
 const calls=[];const api=commerceApi(async(url,options)=>{calls.push([url,options]);return ok({id,state:url.endsWith("/decision")?"approved":"requested"});},identity);
 await api.refund("hotel-a",other,"Synthetic reason");await api.refundAction("hotel-a",id,"approve");
 assert.deepEqual(JSON.parse(calls[0][1].body),{payment_id:other,reason:"Synthetic reason"});assert.deepEqual(JSON.parse(calls[1][1].body),{action:"approve"});
 await assert.rejects(api.refundAction("hotel-a",id,"force"));assert.equal(calls.length,2);
});

test("room and menu writes require current revision and exact nonbinding rate response",async()=>{
 const calls=[];const api=commerceApi(async(url,options)=>{calls.push([url,options]);return ok(url.endsWith("/rooms")?{id,operational_state:"unknown"}:url.endsWith("/venues")?{id}:url.endsWith("/display-rates")?{id,revision:2,rates_binding:false}:{id,revision:2});},identity);
 await api.roomType("hotel-a",{code:"DELUXE",name:"Deluxe",description:"",max_guests:2,published:true,revision:1});
 await api.createRoom("hotel-a",{room_type_id:id,label:"312"});
 await api.displayRate("hotel-a",{room_type_id:id,code:"WEEKEND",currency:"NGN",amount_minor:5000000,start_date:"2026-12-01",end_date:"2026-12-03",revision:1});
 await api.saveMenu("hotel-a",{code:"MEAL",name:"Meal",description:"",price_minor:250000,currency:"NGN",available:true,revision:1});
 await api.createVenue("hotel-a",{name:"Hall",capacity:50});
 assert.deepEqual(calls.map(([url,o])=>[url.split("/staff")[1],o.method]),[["/room-types","PUT"],["/rooms","POST"],["/display-rates","PUT"],["/menu","PUT"],["/venues","POST"]]);
 await assert.rejects(api.roomType("hotel-a",{code:"DELUXE",name:"Deluxe",max_guests:2,published:true,revision:-1}));
 assert.equal(calls.length,5);
});
test("channel reservation lookup is read-only and page-bound",async()=>{
 const calls=[];const api=commerceApi(async(url,options)=>{calls.push([url,options]);return ok({provider:"cloudbeds",page:2,retrieved_at:"2026-11-25T20:00:00Z",reservations:[{reservation_id:"PMS-1",state:"checked_in",arrival:"2026-12-01",departure:"2026-12-03"}]});},identity);
 const d=await api.channels("hotel-a","2026-12-01","2026-12-03",2);
 assert.equal(d.reservations[0].state,"checked_in");assert.equal(calls[0][1].method,"GET");
 await assert.rejects(api.channels("hotel-a","2026-12-01","2026-12-03",1));
});

test("partial refund is keyed and invoice void verifies returned identity and state",async()=>{
 const calls=[];const api=commerceApi(async(url,options)=>{calls.push([url,options]);return ok({id,state:url.endsWith("/void")?"voided":"requested"});},identity);
 await api.requestRefund("hotel-a",id,"Synthetic reason",500,"refund-fixture-key");
 assert.deepEqual(JSON.parse(calls[0][1].body),{payment_id:id,reason:"Synthetic reason",amount_minor:500,request_key:"refund-fixture-key"});
 await assert.rejects(api.requestRefund("hotel-a",id,"Synthetic reason",0,"refund-fixture-key"));
 await api.voidInvoice("hotel-a",id,"Synthetic void reason");assert.equal(calls.length,2);
});
