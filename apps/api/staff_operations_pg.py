"""Property staff directory and shift management."""
from datetime import datetime,timedelta
from uuid import UUID
from fastapi import Header,HTTPException,Query
import hashlib
import json
from typing import Literal
from pydantic import AwareDatetime,BaseModel,Field
from operations_pg import actor,command,encrypt,decrypt

class Profile(BaseModel):
    display_name:str=Field(min_length=2,max_length=120)
    job_title:str=Field(min_length=2,max_length=100)
    employee_reference:str=Field(min_length=2,max_length=80)

class Shift(BaseModel):
    membership_id:UUID
    starts_at:AwareDatetime
    ends_at:AwareDatetime


class Handover(BaseModel):
    recipient_id:UUID
    case_id:UUID|None=None
    request_key:UUID
    note:str=Field(min_length=4,max_length=1500)

class HandoverDecision(BaseModel):
    action:Literal["acknowledge","cancel"]


class AttendanceAction(BaseModel):
    action:Literal["check_in","check_out"]


class LeaveRequest(BaseModel):
    request_key:UUID
    starts_at:AwareDatetime
    ends_at:AwareDatetime
    leave_kind:Literal["annual","sick","personal","other"]

class LeaveDecision(BaseModel):
    action:Literal["approve","decline","withdraw","cancel"]


def install_staff_operations(app):
    base="/api/v1/properties/{slug}/staff"
    @app.post(base+"/leave",status_code=201)
    def request_leave(slug:str,body:LeaveRequest,authorization:str|None=Header(None)):
        return command("SELECT worthkind_flow.request_staff_leave(%s,%s,%s,%s,%s,%s)",
                       (actor(authorization),slug,body.request_key,body.starts_at,body.ends_at,body.leave_kind))[0]

    @app.post(base+"/leave/{leave_id}/decision")
    def decide_leave(slug:str,leave_id:UUID,body:LeaveDecision,authorization:str|None=Header(None)):
        return command("SELECT worthkind_flow.decide_staff_leave(%s,%s,%s,%s)",
                       (actor(authorization),slug,leave_id,body.action))[0]

    @app.get(base+"/leave")
    def leave_requests(slug:str,after:UUID|None=None,limit:int=Query(50,ge=1,le=100),authorization:str|None=Header(None)):
        rows=command("SELECT * FROM worthkind_flow.list_staff_leave(%s,%s,%s,%s)",(actor(authorization),slug,after,limit+1),many=True)
        return {"requests":[{"id":str(r[0]),"membership_id":str(r[1]),"starts_at":r[2].isoformat(),
                "ends_at":r[3].isoformat(),"leave_kind":r[4],"state":r[5],"created_at":r[6].isoformat()} for r in rows[:limit]],
                "next_cursor":str(rows[limit-1][0]) if len(rows)>limit else None}

    @app.post(base+"/shifts/{shift_id}/attendance")
    def record_attendance(slug:str,shift_id:UUID,body:AttendanceAction,authorization:str|None=Header(None)):
        return command("SELECT worthkind_flow.record_staff_attendance(%s,%s,%s,%s)",
                       (actor(authorization),slug,shift_id,body.action))[0]

    @app.get(base+"/attendance")
    def attendance(slug:str,start:AwareDatetime,end:AwareDatetime,after:UUID|None=None,limit:int=Query(50,ge=1,le=100),authorization:str|None=Header(None)):
        rows=command("SELECT * FROM worthkind_flow.list_staff_attendance(%s,%s,%s,%s,%s,%s)",
                     (actor(authorization),slug,start,end,after,limit+1),many=True)
        return {"attendance":[{"shift_id":str(r[0]),"membership_id":str(r[1]),"starts_at":r[2].isoformat(),
                "ends_at":r[3].isoformat(),"checked_in_at":r[4].isoformat() if r[4] else None,
                "checked_out_at":r[5].isoformat() if r[5] else None} for r in rows[:limit]],
                "next_cursor":str(rows[limit-1][0]) if len(rows)>limit else None}

    @app.get(base+"/handover-recipients")
    def recipients(slug:str,after:UUID|None=None,limit:int=Query(50,ge=1,le=100),authorization:str|None=Header(None)):
        rows=command("SELECT * FROM worthkind_flow.handover_recipients(%s,%s,%s,%s)",(actor(authorization),slug,after,limit+1),many=True)
        return {"recipients":[{"membership_id":str(r[0]),"role":r[1],"display_name":r[2]} for r in rows[:limit]],
                "next_cursor":str(rows[limit-1][0]) if len(rows)>limit else None}

    @app.post(base+"/handovers",status_code=201)
    def create_handover(slug:str,body:Handover,authorization:str|None=Header(None)):
        subject=actor(authorization)
        digest=hashlib.sha256(json.dumps(body.model_dump(mode="json"),sort_keys=True).encode()).hexdigest()
        cipher=encrypt({"note":body.note},f"wf:handover:{slug}:{body.request_key}")
        r=command("SELECT * FROM worthkind_flow.create_reception_handover(%s,%s,%s,%s,%s,%s,%s)",
                  (subject,slug,body.recipient_id,body.case_id,body.request_key,digest,cipher))
        return {"id":str(r[0]),"state":r[1],"duplicate":r[2]}

    @app.get(base+"/handovers")
    def handovers(slug:str,after:UUID|None=None,limit:int=Query(50,ge=1,le=100),pending:bool=True,authorization:str|None=Header(None)):
        rows=command("SELECT * FROM worthkind_flow.list_reception_handovers(%s,%s,%s,%s,%s)",(actor(authorization),slug,after,limit+1,pending),many=True)
        return {"handovers":[{"id":str(r[0]),"sender_id":str(r[1]),"recipient_id":str(r[2]),"case_id":str(r[3]) if r[3] else None,
                  "note":decrypt(r[5],f"wf:handover:{slug}:{r[4]}")["note"],"state":r[6],"created_at":r[7].isoformat(),
                  "decided_at":r[8].isoformat() if r[8] else None,"decided_by":str(r[9]) if r[9] else None} for r in rows[:limit]],
                "next_cursor":str(rows[limit-1][0]) if len(rows)>limit else None}

    @app.post(base+"/handovers/{handover_id}/decision")
    def decide_handover(slug:str,handover_id:UUID,body:HandoverDecision,authorization:str|None=Header(None)):
        r=command("SELECT * FROM worthkind_flow.decide_reception_handover(%s,%s,%s,%s)",
                  (actor(authorization),slug,handover_id,body.action))
        return {"id":str(handover_id),"state":r[0],"duplicate":r[1]}

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
