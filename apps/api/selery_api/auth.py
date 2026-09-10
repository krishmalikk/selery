import base64
import hashlib
import hmac
import json
import secrets
import time
from collections import defaultdict
from fastapi import HTTPException,Request

class Auth:
    def __init__(self,config,store=None):
        self.config=config
        self.store=store
        self.attempts=defaultdict(list)
        self.tickets={}
        self.revoked={}

    def login(self,password,ip):
        now=time.time()
        attempts=[t for t in self.attempts[ip] if now-t<300]
        self.attempts[ip]=attempts
        if len(attempts)>=5:raise HTTPException(429,'Too many attempts; retry in five minutes.')
        attempts.append(now)
        if not hmac.compare_digest(password.encode(),self.config.password.encode()):raise HTTPException(401,'Incorrect personal password')
        self.attempts.pop(ip,None)
        return self.issue()

    def issue(self,credential_id=None):
        claims={'exp':int(time.time())+3600,'nonce':secrets.token_hex(16)}
        if credential_id:claims['credential_id']=credential_id
        payload=base64.urlsafe_b64encode(json.dumps(claims).encode()).decode().rstrip('=')
        signature=hmac.new(self.config.session_secret.encode(),payload.encode(),hashlib.sha256).hexdigest()
        return payload+'.'+signature

    def verify(self,token):
        try:
            payload,signature=token.split('.')
            expected=hmac.new(self.config.session_secret.encode(),payload.encode(),hashlib.sha256).hexdigest()
            data=json.loads(base64.urlsafe_b64decode(payload+'='*(-len(payload)%4)))
            valid=hmac.compare_digest(signature,expected) and data['exp']>time.time() and token not in self.revoked
            if valid and data.get('credential_id'):
                valid=bool(self.store and self.store.get('auth_credentials',data['credential_id']))
            return valid
        except (ValueError,KeyError,TypeError):return False

    def require(self,request:Request):
        token=request.headers.get('authorization','').removeprefix('Bearer ') or request.cookies.get('selery_session','')
        if not self.verify(token):raise HTTPException(401,'Sign in to your research workspace')
        if request.method not in ('GET','HEAD','OPTIONS') and not request.headers.get('authorization'):
            origin=request.headers.get('origin')
            if origin and origin not in self.config.allowed_origins:raise HTTPException(403,'Origin is not allowed')
        return token

    def stream_ticket(self,token):
        if not self.verify(token):raise HTTPException(401,'Session expired')
        now=time.time()
        self.tickets={key:value for key,value in self.tickets.items() if value[0]>now}
        ticket=secrets.token_urlsafe(32);self.tickets[ticket]=(now+30,token)
        return ticket

    def consume_ticket(self,ticket):
        expiry,token=self.tickets.pop(ticket,(0,''))
        return token if expiry>time.time() and self.verify(token) else None
