"""Policy-enforced retrieval and Modal answer selection; human paths stay independent."""
import os
import re
from uuid import UUID
import psycopg
from psycopg import errors
from fastapi import Header,Depends,HTTPException
from pydantic import BaseModel,Field,StrictBool
from guest_quota import enforce_guest_quota
from operations_pg import actor
from modal_ai_provider import configuration,select_sources,ModelUnavailable

class Policy(BaseModel):
    revision:int=Field(ge=1)
    guest_chat:StrictBool
    staff_assist:StrictBool
    autonomous_alerts:StrictBool
    voice_enabled:StrictBool
    max_calls_per_day:int=Field(ge=1,le=1000)

class SourcePermission(BaseModel):
    allowed:StrictBool

class Question(BaseModel):
    question:str=Field(min_length=3,max_length=800)
    consent_to_model_processing:StrictBool

def db(query,params,*,policy=False,many=False):
    env="WF_AI_POLICY_POSTGRES_DSN" if policy else "WF_AI_GATEWAY_POSTGRES_DSN"
    dsn=os.getenv(env)
    if not dsn:
        raise HTTPException(503,"AI database unavailable")
    try:
        with psycopg.connect(dsn,connect_timeout=5) as conn:
            with conn.transaction():
                conn.execute("SET LOCAL ROLE wf_ai_policy" if policy else "SET LOCAL ROLE wf_ai_gateway")
                conn.execute("SET LOCAL statement_timeout='5s'")
                cur=conn.execute(query,params)
                return cur.fetchall() if many else cur.fetchone()
    except errors.InsufficientPrivilege:
        raise HTTPException(403,"AI access denied") from None
    except errors.NoDataFound:
        raise HTTPException(404,"AI feature unavailable") from None
    except (errors.CheckViolation,errors.UniqueViolation,errors.SerializationFailure):
        raise HTTPException(409,"AI policy or usage limit conflict") from None
    except errors.InvalidParameterValue:
        raise HTTPException(422,"Invalid AI request") from None
    except psycopg.Error:
        raise HTTPException(503,"AI database unavailable") from None

STOP={"a","an","the","is","are","am","i","me","my","we","you","your","our","it","this","that","what","which","where","when","how","can","could","would","do","does","did","please","tell","about","of","for","to","in","on","at","and","or","have","has","hotel","any"}
def sanitize(question):
    # Best-effort redaction only; callers must never submit personal or confidential data.
    question=re.sub(r"[^\s@]+@[^\s@]+\.[^\s@]+","[redacted]",question)
    question=re.sub(r"(?<!\w)\+?\d[\d\s().-]{5,}\d(?!\w)","[redacted]",question)
    question=re.sub(r"(?i)\b(?:sk|pk|whsec|bearer|password|secret|token)[_-]?[a-z0-9_./=+-]{8,}","[redacted]",question)
    return question

def search_query(question):
    words=list(dict.fromkeys(w.lower() for w in re.findall(r"[^\W\d_]{3,32}",question) if w.lower() not in STOP and w.lower()!="redacted"))[:12]
    return " OR ".join(words)

def handoff(reason):
    return {"status":"handoff","reason":reason,"answer":None,"sources":[],"human_handoff_required":True,"action_executed":False}

def answer(slug,body,subject=None,*,reserved_call=None,voice_renderer=None):
    if not body.consent_to_model_processing:
        return handoff("consent_required")
    try:
        configuration()
    except ModelUnavailable:
        return handoff("model_unavailable")
    question=sanitize(body.question)
    query=search_query(question)
    if not query:
        return handoff("no_relevant_terms")
    try:
        call=reserved_call or db("SELECT worthkind_flow.begin_ai_call(%s,%s,%s)",(slug,subject,"staff_assist" if subject else "guest_chat"))[0]
    except HTTPException as exc:
        if exc.status_code==403:
            raise
        return handoff("policy_or_quota_unavailable")
    try:
        rows=db("SELECT * FROM worthkind_flow.ai_retrieve(%s,%s,%s)",(slug,call,query),many=True)
        sources=[{"id":str(r[0]),"key":r[1],"version":r[2],"title":r[3],"body":r[4]} for r in rows if isinstance(r[3],str) and isinstance(r[4],str)]
        if not sources:
            db("SELECT worthkind_flow.finish_ai_call(%s,%s,%s,%s::uuid[])",(slug,call,"abstained",[]))
            return handoff("no_approved_evidence")
        ids=select_sources(question,sources)
        selected=[s for s in sources if s["id"] in ids]
        state="answered" if selected else "abstained"
        text="\n\n".join(s["body"] for s in selected)
        # Voice synthesis receives only the selected public excerpts, never the raw question.
        audio=voice_renderer(text) if selected and voice_renderer else None
        allowed=db("SELECT worthkind_flow.finish_ai_call(%s,%s,%s,%s::uuid[])",(slug,call,state,[UUID(s["id"]) for s in selected]))[0]
        if not allowed or not selected:
            return handoff("source_or_policy_unavailable")
        # Model prose is deliberately never returned. Verbatim excerpts are attributable to owners.
        return {"status":"answered","answer":text,
                "sources":[{k:v for k,v in s.items() if k!="body"} for s in selected],
                "action_executed":False,"answer_type":"approved_content_excerpt",**({"audio":audio} if audio else {})}
    except (HTTPException,ModelUnavailable):
        try:
            db("SELECT worthkind_flow.finish_ai_call(%s,%s,%s,%s::uuid[])",(slug,call,"failed",[]))
        except HTTPException:
            pass
        return handoff("model_or_retrieval_unavailable")

def install_ai_routes(app):
    base="/api/v1/properties/{slug}"
    @app.get(base+"/staff/ai/policy")
    def get_policy(slug:str,authorization:str|None=Header(None)):
        return db("SELECT worthkind_flow.manage_ai_policy(%s,%s,NULL,NULL,NULL,NULL,NULL,NULL)",(actor(authorization),slug),policy=True)[0]

    @app.put(base+"/staff/ai/policy")
    def save_policy(slug:str,body:Policy,authorization:str|None=Header(None)):
        return db("SELECT worthkind_flow.manage_ai_policy(%s,%s,%s,%s,%s,%s,%s,%s)",(actor(authorization),slug,body.revision,body.guest_chat,body.staff_assist,body.autonomous_alerts,body.voice_enabled,body.max_calls_per_day),policy=True)[0]

    @app.get(base+"/staff/ai/sources")
    def list_sources(slug:str,authorization:str|None=Header(None)):
        return {"sources":db("SELECT worthkind_flow.list_ai_sources(%s,%s)",(actor(authorization),slug),policy=True)[0]}

    @app.get(base+"/staff/ai/usage")
    def usage(slug:str,authorization:str|None=Header(None)):
        return db("SELECT worthkind_flow.ai_usage(%s,%s)",(actor(authorization),slug),policy=True)[0]

    @app.put(base+"/staff/ai/sources/{content_id}")
    def source_permission(slug:str,content_id:UUID,body:SourcePermission,authorization:str|None=Header(None)):
        allowed=db("SELECT worthkind_flow.manage_ai_source(%s,%s,%s,%s)",(actor(authorization),slug,content_id,body.allowed),policy=True)[0]
        return {"id":str(content_id),"allowed":allowed}

    @app.post(base+"/ai/chat",dependencies=[Depends(enforce_guest_quota)])
    def guest(slug:str,body:Question):
        return answer(slug,body)

    @app.post(base+"/staff/ai/chat")
    def staff(slug:str,body:Question,authorization:str|None=Header(None)):
        return answer(slug,body,actor(authorization))
