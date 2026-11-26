"""Server-side Supabase Auth verification; never trust client-supplied identity claims."""
import json
import os
import re
from urllib.error import HTTPError, URLError
from urllib.request import Request, HTTPRedirectHandler, build_opener
from uuid import UUID


class IdentityRejected(ValueError):
    pass


class IdentityUnavailable(RuntimeError):
    pass


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def verified_supabase_subject(authorization):
    if not isinstance(authorization, str) or not re.fullmatch(r"Bearer [A-Za-z0-9_.-]{1,8192}", authorization):
        raise IdentityRejected("Bearer token required")
    url=os.getenv("WF_SUPABASE_URL","").rstrip("/")
    key=os.getenv("WF_SUPABASE_PUBLISHABLE_KEY","")
    if not re.fullmatch(r"https://[a-z0-9]{20}\.supabase\.co",url) or not key:
        raise IdentityUnavailable("Supabase identity configuration unavailable")
    # The public project key identifies the application; authorization is the user token.
    if key.startswith("sb_secret_"):
        raise IdentityUnavailable("Use the publishable project key")
    if not key.startswith("sb_publishable_"):
        # Legacy JWT-form API keys must be explicitly verified as anon keys.
        import jwt
        try:
            if jwt.decode(key,options={"verify_signature":False}).get("role") != "anon":
                raise IdentityUnavailable("Use the publishable project key")
        except jwt.PyJWTError:
            raise IdentityUnavailable("Invalid public project key") from None
    req=Request(url+"/auth/v1/user",headers={"apikey":key,"Authorization":authorization,"Accept":"application/json"})
    try:
        with build_opener(NoRedirect()).open(req,timeout=5) as response:
            raw=response.read(262145)
        if len(raw)>262144:
            raise IdentityUnavailable("Identity response exceeds limit")
        user=json.loads(raw)
    except HTTPError as error:
        if error.code in (400,401,403,404):
            raise IdentityRejected("Bearer token rejected") from None
        raise IdentityUnavailable("Identity service unavailable") from None
    except (URLError,TimeoutError,OSError,ValueError):
        raise IdentityUnavailable("Identity service unavailable") from None
    if not isinstance(user,dict) or user.get("role")!="authenticated" or user.get("is_anonymous") is not False:
        raise IdentityRejected("Permanent authenticated identity required")
    if not (user.get("email_confirmed_at") or user.get("phone_confirmed_at")):
        raise IdentityRejected("Confirmed identity required")
    try:
        return str(UUID(user["id"]))
    except (KeyError,ValueError,TypeError,AttributeError):
        raise IdentityRejected("Invalid provider identity") from None
