"""Stock ledger and purchase approvals, using hotel-scoped PostgreSQL commands."""
from decimal import Decimal
from typing import Literal
from uuid import UUID
from fastapi import Header
from pydantic import BaseModel,Field
from operations_pg import actor,command

class Item(BaseModel):
    sku:str=Field(min_length=2,max_length=60,pattern=r"^[A-Za-z0-9_-]+$")
    name:str=Field(min_length=2,max_length=160)
    unit:str=Field(min_length=1,max_length=24)
    reorder_level:Decimal=Field(default=Decimal(0),ge=0,max_digits=18,decimal_places=3)

class Supplier(BaseModel):
    name:str=Field(min_length=2,max_length=160)
    external_reference:str=Field(min_length=2,max_length=100)

class SupplierDecision(BaseModel):
    state:Literal["approved","suspended"]

class Purchase(BaseModel):
    supplier_id:UUID
    item_id:UUID
    quantity:Decimal=Field(gt=0,max_digits=18,decimal_places=3)
    unit_price_minor:int=Field(ge=0,le=1000000000000)
    currency:str=Field(pattern=r"^[A-Z]{3}$")
    request_key:str=Field(min_length=8,max_length=100,pattern=r"^[A-Za-z0-9_-]+$")

class PurchaseDecision(BaseModel):
    action:Literal["approve","cancel"]

class Movement(BaseModel):
    item_id:UUID
    order_id:UUID|None=None
    quantity_delta:Decimal=Field(max_digits=18,decimal_places=3)
    reason:str=Field(min_length=4,max_length=240)
    request_key:str=Field(min_length=8,max_length=100,pattern=r"^[A-Za-z0-9_-]+$")


def install_procurement_routes(app):
    base="/api/v1/properties/{slug}/staff"
    @app.get(base+"/procurement")
    def overview(slug:str,authorization:str|None=Header(None)):
        return command("SELECT worthkind_flow.procurement_overview(%s,%s)",(actor(authorization),slug))[0]

    @app.post(base+"/stock/items",status_code=201)
    def item(slug:str,body:Item,authorization:str|None=Header(None)):
        r=command("SELECT worthkind_flow.create_stock_item(%s,%s,%s,%s,%s,%s)",(actor(authorization),slug,body.sku,body.name,body.unit,body.reorder_level))
        return {"id":str(r[0])}

    @app.post(base+"/suppliers",status_code=201)
    def supplier(slug:str,body:Supplier,authorization:str|None=Header(None)):
        r=command("SELECT worthkind_flow.create_supplier(%s,%s,%s,%s)",(actor(authorization),slug,body.name,body.external_reference))
        return {"id":str(r[0]),"state":"pending"}

    @app.put(base+"/suppliers/{supplier_id}/state")
    def supplier_state(slug:str,supplier_id:UUID,body:SupplierDecision,authorization:str|None=Header(None)):
        r=command("SELECT worthkind_flow.change_supplier(%s,%s,%s,%s)",(actor(authorization),slug,supplier_id,body.state))
        return {"id":str(supplier_id),"state":r[0]}

    @app.post(base+"/purchase-orders",status_code=201)
    def purchase(slug:str,body:Purchase,authorization:str|None=Header(None)):
        r=command("SELECT worthkind_flow.request_purchase(%s,%s,%s,%s,%s,%s,%s,%s)",(actor(authorization),slug,body.supplier_id,body.item_id,body.quantity,body.unit_price_minor,body.currency,body.request_key))
        return {"id":str(r[0])}

    @app.post(base+"/purchase-orders/{order_id}/decision")
    def purchase_decision(slug:str,order_id:UUID,body:PurchaseDecision,authorization:str|None=Header(None)):
        r=command("SELECT worthkind_flow.decide_purchase(%s,%s,%s,%s)",(actor(authorization),slug,order_id,body.action))
        return {"id":str(order_id),"state":r[0]}

    @app.post(base+"/stock/movements",status_code=201)
    def move(slug:str,body:Movement,authorization:str|None=Header(None)):
        r=command("SELECT * FROM worthkind_flow.move_stock(%s,%s,%s,%s,%s,%s,%s)",(actor(authorization),slug,body.item_id,body.order_id,body.quantity_delta,body.reason,body.request_key))
        return {"id":str(r[0]),"balance":str(r[1]),"duplicate":r[2]}
