"""Personal WebAuthn sign-in, with verified origin, user verification and one-use challenges."""
import hashlib
import hmac
import ipaddress
import json
import os
import secrets
import time
import threading
from datetime import datetime, timezone
from urllib.parse import urlparse
from uuid import uuid4

from fastapi import Depends, HTTPException, Request, Response
from sqlalchemy import delete, select, update
from webauthn import (generate_registration_options, generate_authentication_options,
                      verify_registration_response, verify_authentication_response,
                      options_to_json, base64url_to_bytes)
from webauthn.helpers import bytes_to_base64url
from webauthn.helpers.structs import (AuthenticatorAttachment, AuthenticatorSelectionCriteria,
    ResidentKeyRequirement, UserVerificationRequirement, PublicKeyCredentialDescriptor)
from selery_shared.models import (PasskeyStatus, PasskeyEnrollment, PasskeyOptions,
    PasskeyVerification, PasskeyInfo, SessionResponse)
from .storage import tables

COOKIE = 'selery_passkey_ceremony'
COOKIE_PATH = '/api/v1/auth/passkeys'
TTL = 120

def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()

class Passkeys:
    def __init__(self, store, origin=None):
        self.store = store
        self.origin = (os.getenv('SELERY_PASSKEY_ORIGIN', '') if origin is None else origin).rstrip('/')
        self.rp_id = ''
        self.challenges = {}  # Short-lived only; restart invalidates unfinished ceremonies.
        self.attempts = {}
        self.lock = threading.RLock()
        if self.origin:
            parsed = urlparse(self.origin)
            try:
                ipaddress.ip_address(parsed.hostname or '')
                is_ip = True
            except ValueError:
                is_ip = False
            if (not parsed.hostname or parsed.username or parsed.password or parsed.path
                or parsed.query or parsed.fragment or is_ip
                or (parsed.scheme != 'https' and not (parsed.scheme == 'http' and parsed.hostname == 'localhost'))):
                raise ValueError('SELERY_PASSKEY_ORIGIN must be the exact HTTPS website origin (HTTP localhost only for local development; IP addresses are unsupported).')
            self.rp_id = parsed.hostname
        self.user_id = hashlib.sha256(('selery-personal:' + self.rp_id).encode()).digest()

    def enabled(self):
        if not self.origin:
            raise HTTPException(503, 'Passkey sign-in is not configured for this website yet. Use the workspace password.')

    def credentials(self):
        table = tables['auth_credentials']
        with self.store.engine.connect() as conn:
            return [row[0] for row in conn.execute(select(table.c.payload).where(table.c.payload['rp_id'].as_string() == self.rp_id))]

    def throttle(self, request):
        now = time.time()
        self.attempts = {key: [t for t in values if now-t < 300] for key, values in self.attempts.items() if values and now-values[-1] < 300}
        key = request.client.host if request.client else 'local'
        if len(self.attempts) >= 256 and key not in self.attempts:
            raise HTTPException(429, 'Passkey sign-in is busy; try again later.')
        values = self.attempts.setdefault(key, [])
        if len(values) >= 20:
            raise HTTPException(429, 'Too many passkey attempts; retry in five minutes.')
        values.append(now)

    def begin(self, request, response, kind, session='', name=''):
        with self.lock:
            return self._begin(request, response, kind, session, name)

    def _begin(self, request, response, kind, session='', name=''):
        self.enabled()
        self.throttle(request)
        now = time.time()
        self.challenges = {key: value for key, value in self.challenges.items() if value['expires'] > now}
        if len(self.challenges) >= 200:
            raise HTTPException(429, 'Passkey sign-in is busy; try again shortly.')
        binding = secrets.token_urlsafe(32)
        identifier = uuid4().hex
        challenge = secrets.token_bytes(32)
        self.challenges[identifier] = {'challenge': challenge, 'expires': now+TTL, 'kind': kind,
            'binding': digest(binding), 'session': digest(session), 'name': name}
        response.set_cookie(COOKIE, binding, httponly=True, secure=self.origin.startswith('https:'),
                            samesite='strict', max_age=TTL, path=COOKIE_PATH)
        response.headers['Cache-Control'] = 'no-store'
        return identifier, challenge

    def consume(self, identifier, request, kind, session=''):
        with self.lock:
            return self._consume(identifier, request, kind, session)

    def _consume(self, identifier, request, kind, session=''):
        self.enabled()
        pending = self.challenges.pop(identifier, None)
        if (not pending or pending['expires'] <= time.time() or pending['kind'] != kind
            or not hmac.compare_digest(pending['binding'], digest(request.cookies.get(COOKIE, '')))
            or not hmac.compare_digest(pending['session'], digest(session))):
            raise HTTPException(401, 'Passkey request expired or does not match this browser. Start again.')
        return pending

def register_routes(app, authorized):
    def registry(): return app.state.passkeys

    @app.get('/api/v1/auth/passkeys/status', response_model=PasskeyStatus)
    def status(response: Response):
        reg = registry()
        response.headers['Cache-Control'] = 'no-store'
        return PasskeyStatus(enabled=bool(reg.origin), registered=bool(reg.origin and reg.credentials()),
            reason=None if reg.origin else 'Passkey sign-in is not configured for this website yet.')

    @app.get('/api/v1/auth/passkeys', response_model=list[PasskeyInfo], dependencies=[Depends(authorized)])
    def listing(response: Response):
        response.headers['Cache-Control'] = 'no-store'
        return [PasskeyInfo(id=item['id'], name=item['name'], created_at=item['created_at']) for item in registry().credentials()]

    @app.post('/api/v1/auth/passkeys/register/options', response_model=PasskeyOptions)
    def register_options(body: PasskeyEnrollment, request: Request, response: Response, session=Depends(authorized)):
        reg = registry(); reg.enabled()
        # Fresh password proof prevents a stolen existing session enrolling a new key.
        app.state.auth.login(body.password, request.client.host if request.client else 'local')
        existing = reg.credentials()
        if len(existing) >= 10: raise HTTPException(422, 'Remove an old passkey before adding another.')
        identifier, challenge = reg.begin(request, response, 'register', session, body.name.strip() or 'My passkey')
        options = generate_registration_options(rp_id=reg.rp_id, rp_name='Selery', user_name='Krish',
            user_display_name='Krish', user_id=reg.user_id, challenge=challenge, timeout=TTL*1000,
            authenticator_selection=AuthenticatorSelectionCriteria(authenticator_attachment=AuthenticatorAttachment.PLATFORM,
                resident_key=ResidentKeyRequirement.REQUIRED, user_verification=UserVerificationRequirement.REQUIRED),
            exclude_credentials=[PublicKeyCredentialDescriptor(id=base64url_to_bytes(c['credential_id'])) for c in existing])
        return PasskeyOptions(ceremony_id=identifier, options_json=options_to_json(options))

    @app.post('/api/v1/auth/passkeys/register/verify', response_model=PasskeyInfo)
    def register_verify(body: PasskeyVerification, request: Request, response: Response, session=Depends(authorized)):
        reg = registry(); pending = reg.consume(body.ceremony_id, request, 'register', session)
        try:
            result = verify_registration_response(credential=body.credential_json, expected_challenge=pending['challenge'],
                expected_rp_id=reg.rp_id, expected_origin=reg.origin, require_user_verification=True)
        except Exception:
            raise HTTPException(401, 'Passkey registration could not be verified. Start again.') from None
        identifier = hashlib.sha256(result.credential_id).hexdigest()
        created = datetime.now(timezone.utc).isoformat()
        with reg.lock:
            if reg.store.get('auth_credentials', identifier): raise HTTPException(409, 'This passkey is already registered.')
            if len(reg.credentials()) >= 10: raise HTTPException(422, 'Passkey limit reached.')
            reg.store.put('auth_credentials', {'id':identifier, 'name':pending['name'], 'created_at':created,
                'rp_id':reg.rp_id, 'credential_id':bytes_to_base64url(result.credential_id),
                'public_key':bytes_to_base64url(result.credential_public_key), 'sign_count':result.sign_count}, identifier, immutable=True)
        reg.store.audit('passkey_registered', {'id':identifier})
        response.delete_cookie(COOKIE, path=COOKIE_PATH)
        response.headers['Cache-Control'] = 'no-store'
        return PasskeyInfo(id=identifier, name=pending['name'], created_at=created)

    @app.post('/api/v1/auth/passkeys/login/options', response_model=PasskeyOptions)
    def login_options(request: Request, response: Response):
        reg = registry(); reg.enabled()
        if not reg.credentials(): raise HTTPException(422, 'Sign in with your password once, then add a passkey in Settings.')
        identifier, challenge = reg.begin(request, response, 'login')
        # Discoverable credentials avoid publishing enrolled credential identifiers.
        options = generate_authentication_options(rp_id=reg.rp_id, challenge=challenge, timeout=TTL*1000,
            user_verification=UserVerificationRequirement.REQUIRED)
        return PasskeyOptions(ceremony_id=identifier, options_json=options_to_json(options))

    @app.post('/api/v1/auth/passkeys/login/verify', response_model=SessionResponse)
    def login_verify(body: PasskeyVerification, request: Request, response: Response):
        reg = registry(); pending = reg.consume(body.ceremony_id, request, 'login')
        try:
            data = json.loads(body.credential_json)
            identifier = hashlib.sha256(base64url_to_bytes(data['id'])).hexdigest()
            saved = reg.store.get('auth_credentials', identifier)
            if not saved or saved['rp_id'] != reg.rp_id: raise ValueError('Unknown credential')
            handle = data.get('response', {}).get('userHandle')
            if handle and base64url_to_bytes(handle) != reg.user_id: raise ValueError('Wrong user handle')
            result = verify_authentication_response(credential=data, expected_challenge=pending['challenge'],
                expected_rp_id=reg.rp_id, expected_origin=reg.origin,
                credential_public_key=base64url_to_bytes(saved['public_key']),
                credential_current_sign_count=saved['sign_count'], require_user_verification=True)
            # Detect a concurrent credential deletion/counter update after verification.
            table = tables['auth_credentials']
            with reg.store.engine.begin() as conn:
                changed = conn.execute(update(table).where(table.c.id==identifier,
                    table.c.payload['sign_count'].as_integer()==saved['sign_count']).values(
                    payload={**saved, 'sign_count':result.new_sign_count}))
                if changed.rowcount != 1: raise ValueError('Credential changed')
        except Exception:
            raise HTTPException(401, 'Passkey sign-in could not be verified. Try again or use your workspace password.') from None
        token = app.state.auth.issue(credential_id=identifier)
        response.set_cookie('selery_session',token,max_age=3600,httponly=True,
            secure=reg.origin.startswith('https:'),samesite='lax',path='/')
        response.delete_cookie(COOKIE, path=COOKIE_PATH)
        response.headers['Cache-Control'] = 'no-store'
        reg.store.audit('passkey_login', {'id':identifier})
        return SessionResponse(token=token,expires_in=3600)

    @app.post('/api/v1/auth/passkeys/{identifier}/delete', dependencies=[Depends(authorized)])
    def remove(identifier: str, response: Response):
        reg=registry(); table=tables['auth_credentials']
        with reg.store.engine.begin() as conn:
            conn.execute(delete(table).where(table.c.id==identifier,table.c.payload['rp_id'].as_string()==reg.rp_id))
        response.headers['Cache-Control']='no-store'
        reg.store.audit('passkey_removed', {'id':identifier[:64]})
        return {'ok':True}
