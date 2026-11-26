"""Voice turn transport to private Modal ASR/TTS services. No arbitrary speech endpoint."""
import base64
import io
import json
import os
import wave
from urllib.parse import urlsplit
from urllib.request import Request,build_opener
from urllib.error import HTTPError,URLError
from fastapi import Header,HTTPException,Request as Incoming,Depends
from starlette.concurrency import run_in_threadpool
from supabase_identity import NoRedirect
from guest_quota import enforce_guest_quota
from ai_gateway import db,Question,answer,handoff
from modal_ai_provider import configuration,ModelUnavailable

MAX_INPUT=640128
MAX_OUTPUT=4*1024*1024

def endpoint(name,path):
    url=os.getenv(name,"")
    try:
        parsed=urlsplit(url)
    except ValueError:
        raise ModelUnavailable("Voice endpoint unavailable") from None
    if (parsed.scheme!="https" or not parsed.hostname or not parsed.hostname.endswith(".modal.run")
        or parsed.netloc!=parsed.hostname or parsed.path!=path or parsed.query or parsed.fragment):
        raise ModelUnavailable("Voice endpoint unavailable")
    return url

def voice_config():
    if os.getenv("WF_MODAL_VOICE_ENABLED")!="1":
        raise ModelUnavailable("Voice unavailable")
    _,_,key,secret=configuration()
    return endpoint("WF_MODAL_ASR_URL","/transcribe"),endpoint("WF_MODAL_TTS_URL","/synthesize"),key,secret

def validate_input(raw):
    try:
        with wave.open(io.BytesIO(raw),"rb") as wav:
            if (wav.getnchannels(),wav.getsampwidth(),wav.getframerate(),wav.getcomptype())!=(1,2,16000,"NONE"):
                raise ValueError()
            frames=wav.getnframes()
            if not 1600<=frames<=320000 or len(wav.readframes(frames))!=frames*2:
                raise ValueError()
    except (wave.Error,EOFError,ValueError,OverflowError):
        raise HTTPException(422,"Use mono PCM WAV, 16 kHz, 16-bit, 0.1 to 20 seconds") from None

def post(url,key,secret,data,content_type,max_bytes):
    req=Request(url,data=data,method="POST",headers={"Modal-Key":key,"Modal-Secret":secret,
                 "Content-Type":content_type,"Accept":"application/json"})
    try:
        with build_opener(NoRedirect()).open(req,timeout=30) as response:
            raw=response.read(max_bytes+1)
        if len(raw)>max_bytes:
            raise ValueError()
        return raw
    except (HTTPError,URLError,TimeoutError,OSError,ValueError):
        raise ModelUnavailable("Voice provider unavailable") from None

def transcribe(cfg,raw):
    try:
        result=json.loads(post(cfg[0],cfg[2],cfg[3],raw,"audio/wav",8192))
        text=result["text"]
        if not isinstance(text,str) or not 3<=len(text.strip())<=800:
            raise ValueError()
        return text.strip()
    except (ValueError,KeyError,TypeError):
        raise ModelUnavailable("Invalid transcription") from None

def synthesize(cfg,text):
    # Bound maximum speech length; a longer verified response can still be read as text.
    if len(text)>1200:
        return None
    try:
        result=json.loads(post(cfg[1],cfg[2],cfg[3],json.dumps({"text":text}).encode(),"application/json",MAX_OUTPUT*2))
        if result.get("mime_type")!="audio/wav":
            raise ValueError()
        raw=base64.b64decode(result["audio_base64"],validate=True)
        if not 44<len(raw)<=MAX_OUTPUT:
            raise ValueError()
        with wave.open(io.BytesIO(raw),"rb") as w:
            if w.getnchannels()!=1 or w.getsampwidth()!=2 or w.getframerate() not in (16000,22050,24000,44100,48000) or not 0<w.getnframes()<=60*w.getframerate():
                raise ValueError()
            if len(w.readframes(w.getnframes()))!=2*w.getnframes():
                raise ValueError()
        return {"mime_type":"audio/wav","base64":base64.b64encode(raw).decode("ascii")}
    except (ModelUnavailable,ValueError,KeyError,TypeError,AttributeError,wave.Error,EOFError):
        return None

def voice_turn(slug,raw):
    validate_input(raw)
    try:
        cfg=voice_config()
    except ModelUnavailable:
        return handoff("voice_unavailable")
    try:
        call=db("SELECT worthkind_flow.begin_ai_call(%s,NULL,'voice')",(slug,))[0]
    except HTTPException:
        return handoff("voice_policy_or_quota_unavailable")
    try:
        question=transcribe(cfg,raw)
        response=answer(slug,Question(question=question,consent_to_model_processing=True),
                        reserved_call=call,voice_renderer=lambda text:synthesize(cfg,text))
        return {**response,"voice_output_available":bool(response.get("audio"))}
    except ModelUnavailable:
        return handoff("transcription_unavailable")
    finally:
        # No-op if answer already finalized the reserved call.
        try:
            db("SELECT worthkind_flow.finish_ai_call(%s,%s,'failed','{}'::uuid[])",(slug,call))
        except HTTPException:
            pass

def install_voice_routes(app):
    @app.post("/api/v1/properties/{slug}/ai/voice",dependencies=[Depends(enforce_guest_quota)])
    async def voice(slug:str,request:Incoming,x_voice_consent:str|None=Header(None)):
        if x_voice_consent!="true":
            return handoff("voice_processing_consent_required")
        if request.headers.get("content-type","").split(";")[0].strip()!="audio/wav":
            raise HTTPException(415,"Expected WAV audio")
        raw=bytearray()
        async for chunk in request.stream():
            if len(raw)+len(chunk)>MAX_INPUT:
                raise HTTPException(413,"Audio exceeds voice turn limit")
            raw.extend(chunk)
        return await run_in_threadpool(voice_turn,slug,bytes(raw))
