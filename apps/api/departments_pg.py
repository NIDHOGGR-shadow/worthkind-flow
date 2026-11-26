"""Event venue operations and HR application boundaries."""
from datetime import date,timedelta
from typing import Literal
from uuid import UUID
from fastapi import Header,Depends,HTTPException,Query
from pydantic import AwareDatetime,BaseModel,Field,StrictBool
from guest_records_pg import proof
from guest_quota import enforce_guest_quota
from operations_pg import actor,command,encrypt,decrypt

class Venue(BaseModel):
    name:str=Field(min_length=2,max_length=120)
    capacity:int=Field(ge=1,le=100000)

class VenueRequest(BaseModel):
    venue_id:UUID
    starts_at:AwareDatetime
    ends_at:AwareDatetime
    attendance:int=Field(ge=1,le=100000)
    request_key:str=Field(min_length=8,max_length=100,pattern=r"^[A-Za-z0-9_-]+$")

class VenueDecision(BaseModel):
    action:Literal["review","accept","decline","cancel"]

class Vacancy(BaseModel):
    title:str=Field(min_length=2,max_length=160)
    description:str=Field(min_length=8,max_length=4000)
    deadline:date

class VacancyDecision(BaseModel):
    action:Literal["publish","close"]

class Application(BaseModel):
    vacancy_id:UUID
    statement:str=Field(min_length=8,max_length=4000)
    qualifications:str=Field(default="",max_length=3000)
    consent:StrictBool

class ApplicationDecision(BaseModel):
    action:Literal["review","shortlist","reject","select"]


def install_department_routes(app):
    base="/api/v1/properties/{slug}"
    g=base+"/guest/cases/{case_id}"
    @app.get(g+"/venue-requests",dependencies=[Depends(enforce_guest_quota)])
    def guest_venues(slug:str,case_id:UUID,after:UUID|None=None,limit:int=Query(50,ge=1,le=100),x_receipt_token:str|None=Header(None)):
        rows=command("SELECT * FROM worthkind_flow.guest_venue_requests(%s,%s,%s,%s,%s)",
                     (slug,case_id,proof(x_receipt_token),after,limit+1),many=True,guest=True)
        return {"requests":[{"id":str(r[0]),"venue_id":str(r[1]),"venue_name":r[2],"starts_at":r[3].isoformat(),
                             "ends_at":r[4].isoformat(),"attendance":r[5],"state":r[6]} for r in rows[:limit]],
                "next_cursor":str(rows[limit-1][0]) if len(rows)>limit else None}

    @app.get(g+"/applications",dependencies=[Depends(enforce_guest_quota)])
    def guest_applications(slug:str,case_id:UUID,after:UUID|None=None,limit:int=Query(50,ge=1,le=100),x_receipt_token:str|None=Header(None)):
        rows=command("SELECT * FROM worthkind_flow.guest_applications(%s,%s,%s,%s,%s)",
                     (slug,case_id,proof(x_receipt_token),after,limit+1),many=True,guest=True)
        return {"applications":[{"id":str(r[0]),"vacancy_id":str(r[1]),"title":r[2],"state":r[3],"created_at":r[4].isoformat()} for r in rows[:limit]],
                "next_cursor":str(rows[limit-1][0]) if len(rows)>limit else None}

    @app.post(g+"/applications/{application_id}/withdraw",dependencies=[Depends(enforce_guest_quota)])
    def withdraw(slug:str,case_id:UUID,application_id:UUID,x_receipt_token:str|None=Header(None)):
        r=command("SELECT worthkind_flow.withdraw_guest_application(%s,%s,%s,%s)",
                  (slug,case_id,proof(x_receipt_token),application_id),guest=True)
        return {"id":str(application_id),"state":r[0]}

    @app.get(base+"/venues")
    def venues(slug:str):
        rows=command("SELECT * FROM worthkind_flow.public_venues(%s)",(slug,),many=True,public=True)
        return {"venues":[{"id":str(r[0]),"name":r[1],"capacity":r[2]} for r in rows]}

    @app.post(base+"/staff/venues",status_code=201)
    def venue(slug:str,body:Venue,authorization:str|None=Header(None)):
        r=command("SELECT worthkind_flow.create_venue(%s,%s,%s,%s)",(actor(authorization),slug,body.name,body.capacity))
        return {"id":str(r[0])}

    @app.post(g+"/venue-requests",status_code=201,dependencies=[Depends(enforce_guest_quota)])
    def request_venue(slug:str,case_id:UUID,body:VenueRequest,x_receipt_token:str|None=Header(None)):
        if body.ends_at<=body.starts_at or body.ends_at-body.starts_at>timedelta(days=7):
            raise HTTPException(422,"Invalid event date range")
        r=command("SELECT * FROM worthkind_flow.request_venue_with_state(%s,%s,%s,%s,%s,%s,%s,%s)",
                  (slug,case_id,proof(x_receipt_token),body.venue_id,body.starts_at,body.ends_at,body.attendance,body.request_key),guest=True)
        return {"id":str(r[0]),"state":r[1]}

    @app.get(base+"/staff/venue-requests")
    def events(slug:str,authorization:str|None=Header(None)):
        return {"requests":command("SELECT worthkind_flow.events_queue(%s,%s)",(actor(authorization),slug))[0]}

    @app.post(base+"/staff/venue-requests/{request_id}/decision")
    def decide_venue(slug:str,request_id:UUID,body:VenueDecision,authorization:str|None=Header(None)):
        r=command("SELECT worthkind_flow.decide_venue(%s,%s,%s,%s)",(actor(authorization),slug,request_id,body.action))
        return {"id":str(request_id),"state":r[0]}

    @app.get(base+"/vacancies")
    def vacancies(slug:str):
        rows=command("SELECT * FROM worthkind_flow.public_vacancies(%s)",(slug,),many=True,public=True)
        return {"vacancies":[{"id":str(r[0]),"title":r[1],"description":r[2],"deadline":r[3].isoformat()} for r in rows]}

    @app.post(base+"/staff/vacancies",status_code=201)
    def vacancy(slug:str,body:Vacancy,authorization:str|None=Header(None)):
        r=command("SELECT worthkind_flow.create_vacancy(%s,%s,%s,%s,%s)",(actor(authorization),slug,body.title,body.description,body.deadline))
        return {"id":str(r[0]),"state":"draft"}

    @app.post(base+"/staff/vacancies/{vacancy_id}/decision")
    def decide_vacancy(slug:str,vacancy_id:UUID,body:VacancyDecision,authorization:str|None=Header(None)):
        r=command("SELECT worthkind_flow.decide_vacancy(%s,%s,%s,%s)",(actor(authorization),slug,vacancy_id,body.action))
        return {"id":str(vacancy_id),"state":r[0]}

    @app.post(g+"/applications",status_code=201,dependencies=[Depends(enforce_guest_quota)])
    def apply(slug:str,case_id:UUID,body:Application,x_receipt_token:str|None=Header(None)):
        if not body.consent:
            raise HTTPException(422,"Application processing consent required")
        h=proof(x_receipt_token)
        cipher=encrypt({"statement":body.statement,"qualifications":body.qualifications,"consent":True},f"wf:application:{slug}:{case_id}:{body.vacancy_id}")
        r=command("SELECT worthkind_flow.submit_application(%s,%s,%s,%s,%s)",(slug,case_id,h,body.vacancy_id,cipher),guest=True)
        return {"id":str(r[0]),"state":"submitted"}

    @app.get(base+"/staff/applications")
    def applications(slug:str,authorization:str|None=Header(None)):
        rows=command("SELECT * FROM worthkind_flow.recruitment_queue(%s,%s)",(actor(authorization),slug),many=True)
        return {"applications":[{"id":str(r[0]),"vacancy_id":str(r[1]),"case_id":str(r[2]),"state":r[3],
            **decrypt(r[4],f"wf:application:{slug}:{r[2]}:{r[1]}"),"created_at":r[5].isoformat()} for r in rows]}

    @app.post(base+"/staff/applications/{application_id}/decision")
    def decide_application(slug:str,application_id:UUID,body:ApplicationDecision,authorization:str|None=Header(None)):
        r=command("SELECT worthkind_flow.review_application(%s,%s,%s,%s)",(actor(authorization),slug,application_id,body.action))
        return {"id":str(application_id),"state":r[0]}
