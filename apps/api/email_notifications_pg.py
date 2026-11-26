"""Reception-authorized service email queue; no claim of delivery at enqueue."""
from uuid import UUID
from fastapi import Header
from pydantic import BaseModel,Field
from operations_pg import actor,command

class QueueEmail(BaseModel):
    event_id:UUID
    verification_reference:str=Field(min_length=8,max_length=240)

def install_email_notifications(app):
    path="/api/v1/properties/{slug}/staff/cases/{case_id}/notifications"
    @app.get(path)
    def notifications(slug:str,case_id:UUID,authorization:str|None=Header(None)):
        return {"notifications":command("SELECT worthkind_flow.list_case_email_notifications(%s,%s,%s)",(actor(authorization),slug,case_id))[0]}
    @app.post(path,status_code=201)
    def queue(slug:str,case_id:UUID,body:QueueEmail,authorization:str|None=Header(None)):
        return command("SELECT worthkind_flow.queue_email_notification(%s,%s,%s,%s,%s)",
                       (actor(authorization),slug,case_id,body.event_id,body.verification_reference))[0]
