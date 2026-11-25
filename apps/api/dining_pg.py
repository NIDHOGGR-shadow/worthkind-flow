"""Hotel-operated dining orders. No POS or payment confirmation is inferred."""
from typing import Literal
from uuid import UUID
from fastapi import Header,HTTPException
from pydantic import BaseModel,Field
from psycopg.types.json import Jsonb
from operations_pg import actor,command

class MenuItem(BaseModel):
    code:str=Field(min_length=2,max_length=60,pattern=r"^[A-Za-z0-9_-]+$")
    name:str=Field(min_length=2,max_length=160)
    description:str=Field(default="",max_length=1000)
    price_minor:int=Field(ge=0,le=1000000000000)
    currency:str=Field(pattern=r"^[A-Z]{3}$")
    available:bool=False
    revision:int=Field(ge=0)

class Line(BaseModel):
    item_id:UUID
    quantity:int=Field(ge=1,le=100)

class Order(BaseModel):
    request_key:str=Field(min_length=8,max_length=100,pattern=r"^[A-Za-z0-9_-]+$")
    room_id:UUID|None=None
    lines:list[Line]=Field(min_length=1,max_length=50)

class Transition(BaseModel):
    action:Literal["accept","prepare","ready","serve","reject","cancel"]


def install_dining_routes(app):
    base="/api/v1/properties/{slug}"
    @app.get(base+"/menu")
    def menu(slug:str):
        rows=command("SELECT * FROM worthkind_flow.list_menu(%s)",(slug,),many=True,public=True)
        return {"items":[{"id":str(r[0]),"code":r[1],"name":r[2],"description":r[3],"price_minor":r[4],"currency":r[5]} for r in rows]}

    @app.put(base+"/staff/menu")
    def save(slug:str,body:MenuItem,authorization:str|None=Header(None)):
        r=command("SELECT * FROM worthkind_flow.save_menu_item(%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                  (actor(authorization),slug,body.code,body.name,body.description,body.price_minor,body.currency,body.available,body.revision))
        return {"id":str(r[0]),"revision":r[1]}

    @app.post(base+"/staff/dining/orders",status_code=201)
    def order(slug:str,body:Order,authorization:str|None=Header(None)):
        if len({line.item_id for line in body.lines})!=len(body.lines):
            raise HTTPException(422,"Duplicate menu item")
        r=command("SELECT * FROM worthkind_flow.create_dining_order(%s,%s,%s,%s,%s)",
                  (actor(authorization),slug,body.request_key,body.room_id,Jsonb([line.model_dump(mode="json") for line in body.lines])))
        return {"id":str(r[0]),"state":r[1],"total_minor":r[2],"currency":r[3],"duplicate":r[4],"payment_confirmed":False}

    @app.get(base+"/staff/dining/orders")
    def queue(slug:str,authorization:str|None=Header(None)):
        return {"orders":command("SELECT worthkind_flow.dining_queue(%s,%s)",(actor(authorization),slug))[0],"pos_connected":False}

    @app.post(base+"/staff/dining/orders/{order_id}/transition")
    def change(slug:str,order_id:UUID,body:Transition,authorization:str|None=Header(None)):
        r=command("SELECT worthkind_flow.transition_dining_order(%s,%s,%s,%s)",(actor(authorization),slug,order_id,body.action))
        return {"id":str(order_id),"state":r[0],"payment_confirmed":False}
