"""Property staff directory and shift management."""
from datetime import datetime,timedelta
from uuid import UUID
from fastapi import Header,HTTPException
from pydantic import AwareDatetime,BaseModel,Field
from operations_pg import actor,command

class Profile(BaseModel):
    display_name:str=Field(min_length=2,max_length=120)
    job_title:str=Field(min_length=2,max_length=100)
    employee_reference:str=Field(min_length=2,max_length=80)

class Shift(BaseModel):
    membership_id:UUID
    starts_at:AwareDatetime
    ends_at:AwareDatetime


def install_staff_operations(app):
    base="/api/v1/properties/{slug}/staff"
    @app.get(base+"/schedule")
    def schedule(slug:str,start:AwareDatetime,end:AwareDatetime,authorization:str|None=Header(None)):
        if end<=start or end-start>timedelta(days=93):
            raise HTTPException(422,"Invalid schedule range")
        return command("SELECT worthkind_flow.staff_schedule(%s,%s,%s,%s)",(actor(authorization),slug,start,end))[0]

    @app.put(base+"/profiles/{member_id}")
    def profile(slug:str,member_id:UUID,body:Profile,authorization:str|None=Header(None)):
        r=command("SELECT worthkind_flow.save_staff_profile(%s,%s,%s,%s,%s,%s)",
                  (actor(authorization),slug,member_id,body.display_name,body.job_title,body.employee_reference))
        return {"membership_id":str(r[0])}

    @app.post(base+"/shifts",status_code=201)
    def create(slug:str,body:Shift,authorization:str|None=Header(None)):
        if body.ends_at<=body.starts_at or body.ends_at-body.starts_at>timedelta(days=1):
            raise HTTPException(422,"Invalid shift range")
        r=command("SELECT worthkind_flow.schedule_staff_shift(%s,%s,%s,%s,%s)",
                  (actor(authorization),slug,body.membership_id,body.starts_at,body.ends_at))
        return {"id":str(r[0]),"state":"scheduled"}

    @app.post(base+"/shifts/{shift_id}/cancel")
    def cancel(slug:str,shift_id:UUID,authorization:str|None=Header(None)):
        r=command("SELECT worthkind_flow.cancel_staff_shift(%s,%s,%s)",(actor(authorization),slug,shift_id))
        return {"id":str(r[0]),"state":"cancelled"}
