"""Real ES256 signatures and CBOR attestations; no biometric hardware or network."""
import hashlib
import json
import os
import time
import cbor2
import pytest
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi.testclient import TestClient
from webauthn.helpers import bytes_to_base64url as b64
from selery_api.config import Config
from selery_api.main import create_app
from selery_api.passkeys import COOKIE, Passkeys
from selery_api.storage import Store

ORIGIN='http://localhost'
RP='localhost'
PASSWORD='passkey-fixture-password'
PATH='/api/v1/auth/passkeys'

@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv('SELERY_PASSKEY_ORIGIN',ORIGIN)
    cfg=Config('https://paper-api.alpaca.markets','','',PASSWORD,'s'*48,'fixtures','sqlite:///:memory:',(ORIGIN,),0)
    with TestClient(create_app(cfg)) as client: yield client

def login(client):
    response=client.post('/api/v1/auth/login',json={'password':PASSWORD})
    assert response.status_code==200
    return response.json()['token']

def start_register(client,password=PASSWORD):
    return client.post(PATH+'/register/options',json={'password':password,'name':'Test Mac'})

def registration(start, key, credential_id, origin=ORIGIN, flags=0x45, rp=RP):
    public=key.public_key().public_numbers()
    cose=cbor2.dumps({1:2,3:-7,-1:1,-2:public.x.to_bytes(32,'big'),-3:public.y.to_bytes(32,'big')})
    auth=hashlib.sha256(rp.encode()).digest()+bytes([flags])+bytes(4)+bytes(16)+len(credential_id).to_bytes(2,'big')+credential_id+cose
    client_data=json.dumps({'type':'webauthn.create','challenge':json.loads(start['options_json'])['challenge'],'origin':origin}).encode()
    return {'id':b64(credential_id),'rawId':b64(credential_id),'type':'public-key',
        'response':{'clientDataJSON':b64(client_data),'attestationObject':b64(cbor2.dumps({'fmt':'none','attStmt':{},'authData':auth}))}}

def assertion(start, key, credential_id, origin=ORIGIN, flags=0x05, count=1, rp=RP):
    auth=hashlib.sha256(rp.encode()).digest()+bytes([flags])+count.to_bytes(4,'big')
    client_data=json.dumps({'type':'webauthn.get','challenge':json.loads(start['options_json'])['challenge'],'origin':origin}).encode()
    signature=key.sign(auth+hashlib.sha256(client_data).digest(),ec.ECDSA(hashes.SHA256()))
    return {'id':b64(credential_id),'rawId':b64(credential_id),'type':'public-key','response':{
        'clientDataJSON':b64(client_data),'authenticatorData':b64(auth),'signature':b64(signature),
        'userHandle':b64(hashlib.sha256(('selery-personal:'+RP).encode()).digest())}}

def verify(client,kind,start,credential):
    return client.post(PATH+'/'+kind+'/verify',json={'ceremony_id':start['ceremony_id'],'credential_json':json.dumps(credential)})

def enroll(client):
    login(client)
    start=start_register(client).json()
    key=ec.generate_private_key(ec.SECP256R1());identifier=os.urandom(32)
    response=verify(client,'register',start,registration(start,key,identifier))
    assert response.status_code==200,response.text
    return key,identifier,response.json()['id']

def test_registration_requires_session_and_fresh_password(client):
    assert start_register(client).status_code==401
    login(client)
    assert start_register(client,'wrong').status_code==401
    start=start_register(client)
    assert start.status_code==200
    cookie=start.headers['set-cookie']
    assert 'HttpOnly' in cookie and 'SameSite=strict' in cookie
    options=json.loads(start.json()['options_json'])
    assert options['authenticatorSelection']['userVerification']=='required'
    assert options['authenticatorSelection']['residentKey']=='required'
    assert options['authenticatorSelection']['authenticatorAttachment']=='platform'

def test_real_registration_and_assertion_issue_session_and_revoke(client):
    key,identifier,stored_id=enroll(client)
    assert client.get(PATH+'/status').json()['registered']
    record=client.app.state.store.get('auth_credentials',stored_id)
    assert record['public_key'] and 'private_key' not in record
    assert client.get(PATH).json()[0]['name']=='Test Mac'
    client.post('/api/v1/auth/logout')
    assert client.get('/api/v1/settings').status_code==401
    start=client.post(PATH+'/login/options').json()
    response=verify(client,'login',start,assertion(start,key,identifier))
    assert response.status_code==200,response.text
    token=response.json()['token']
    assert client.get('/api/v1/settings').status_code==200
    assert client.app.state.store.get('auth_credentials',stored_id)['sign_count']==1
    assert client.post(PATH+'/'+stored_id+'/delete').status_code==200
    assert client.get('/api/v1/settings',headers={'Authorization':'Bearer '+token}).status_code==401
    assert not client.get(PATH+'/status').json()['registered']

@pytest.mark.parametrize('changes',[{'origin':'https://attacker.invalid'},{'flags':0x41},{'rp':'attacker.invalid'}])
def test_bad_registration_rejected(client,changes):
    login(client);start=start_register(client).json()
    key=ec.generate_private_key(ec.SECP256R1())
    response=verify(client,'register',start,registration(start,key,os.urandom(32),**changes))
    assert response.status_code==401
    assert client.app.state.store.list('auth_credentials')==[]

@pytest.mark.parametrize('changes',[{'origin':'https://attacker.invalid'},{'flags':0x01},{'rp':'attacker.invalid'}])
def test_bad_assertion_rejected(client,changes):
    key,identifier,_=enroll(client);client.post('/api/v1/auth/logout')
    start=client.post(PATH+'/login/options').json()
    response=verify(client,'login',start,assertion(start,key,identifier,**changes))
    assert response.status_code==401
    assert client.get('/api/v1/settings').status_code==401

def test_signature_tampering_counter_replay_and_challenge_replay(client):
    key,identifier,_=enroll(client);client.post('/api/v1/auth/logout')
    start=client.post(PATH+'/login/options').json()
    wrong=assertion(start,ec.generate_private_key(ec.SECP256R1()),identifier)
    assert verify(client,'login',start,wrong).status_code==401
    start=client.post(PATH+'/login/options').json()
    valid=assertion(start,key,identifier)
    assert verify(client,'login',start,valid).status_code==200
    assert verify(client,'login',start,valid).status_code==401
    start=client.post(PATH+'/login/options').json()
    assert verify(client,'login',start,assertion(start,key,identifier,count=1)).status_code==401

@pytest.mark.parametrize('failure',['expiry','cookie','restart','user_handle'])
def test_challenge_is_bound_and_one_use(client,failure):
    key,identifier,_=enroll(client);client.post('/api/v1/auth/logout')
    start=client.post(PATH+'/login/options').json()
    signed=assertion(start,key,identifier)
    if failure=='expiry':client.app.state.passkeys.challenges[start['ceremony_id']]['expires']=time.time()-1
    if failure=='cookie':client.cookies.clear()
    if failure=='restart':client.app.state.passkeys=Passkeys(client.app.state.store,ORIGIN)
    if failure=='user_handle':signed['response']['userHandle']=b64(b'another-user')
    assert verify(client,'login',start,signed).status_code==401
    assert client.get('/api/v1/settings').status_code==401

def test_registration_bound_to_original_session(client):
    login(client);start=start_register(client).json()
    key=ec.generate_private_key(ec.SECP256R1());signed=registration(start,key,os.urandom(32))
    login(client)
    assert verify(client,'register',start,signed).status_code==401

def test_disabled_and_request_limits(client):
    client.app.state.passkeys=Passkeys(client.app.state.store,'')
    assert client.get(PATH+'/status').json()['enabled'] is False
    assert client.post(PATH+'/login/options').status_code==503
    client.app.state.passkeys=Passkeys(client.app.state.store,ORIGIN)
    enroll(client)
    for _ in range(19): assert client.post(PATH+'/login/options').status_code==200
    assert client.post(PATH+'/login/options').status_code==429
    assert client.post(PATH+'/login/verify',json={'ceremony_id':'a'*32,'credential_json':'x'*20001}).status_code==422

@pytest.mark.parametrize('origin',['http://example.com','https://example.com/path','https://user@example.com','https://example.com?query=yes','http://127.0.0.1:3000','https://127.0.0.1','https://[::1]'])
def test_origin_configuration_rejects_unsafe_values(origin):
    with pytest.raises(ValueError):Passkeys(Store('sqlite:///:memory:'),origin)

def test_secure_ceremony_cookie_on_https(client):
    client.app.state.passkeys=Passkeys(client.app.state.store,'https://selery.example')
    login(client)
    response=start_register(client)
    assert response.status_code==200
    assert 'Secure' in response.headers['set-cookie']

def test_synced_passkey_zero_counter_still_requires_a_new_challenge(client):
    key,identifier,_=enroll(client)
    for _ in range(2):
        start=client.post(PATH+'/login/options').json()
        signed=assertion(start,key,identifier,count=0)
        assert verify(client,'login',start,signed).status_code==200
        assert verify(client,'login',start,signed).status_code==401

def test_concurrent_pruning_cannot_resurrect_a_consumed_challenge(client):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event
    from fastapi import HTTPException, Request, Response
    enroll(client)
    start=client.post(PATH+'/login/options').json()
    reg=client.app.state.passkeys
    copied,release,consuming,consumed=Event(),Event(),Event(),Event()
    class PausedItems(dict):
        def items(self):
            snapshot=list(super().items())
            copied.set()
            assert release.wait(3)
            return snapshot
    reg.challenges=PausedItems(reg.challenges)
    request=Request({'type':'http','headers':[(b'cookie',(COOKIE+'='+client.cookies.get(COOKIE)).encode())],
        'client':('testclient',1234)})
    def consume():
        consuming.set()
        result=reg.consume(start['ceremony_id'],request,'login')
        consumed.set()
        return result
    with ThreadPoolExecutor(max_workers=2) as pool:
        begin_future=pool.submit(reg.begin,request,Response(),'login')
        assert copied.wait(3)
        consume_future=pool.submit(consume)
        assert consuming.wait(3)
        # A verify arriving during a prune must wait for the same lock.
        completed_while_pruning=consumed.wait(.05)
        release.set()
        begin_future.result(timeout=3);consume_future.result(timeout=3)
    assert not completed_while_pruning
    assert start['ceremony_id'] not in reg.challenges
    with pytest.raises(HTTPException):reg.consume(start['ceremony_id'],request,'login')
