"""Explicit read-only credential probe; no public people, persistence or LLM use."""
import asyncio
import json
import sys
from datetime import datetime,timezone
from pathlib import Path
from uuid import uuid4

import httpx
from dotenv import load_dotenv

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'apps/api'),str(ROOT/'packages/shared/python')]
from selery_api.public_traders import PublicConfig

async def verify():
    load_dotenv(ROOT/'.env')
    result={'checked_at':datetime.now(timezone.utc).isoformat(),'operation':'instrument_display_metadata',
        'public_record_access_verified':False,'records_stored':False,'llm_requested':False}
    try:
        cfg=PublicConfig.load()
        if not cfg.api_key or not cfg.user_key:
            result['status']='credentials_missing'; return result
        # Authentication qualification is separate from public-record storage rights.
        async with httpx.AsyncClient(timeout=20,follow_redirects=False) as client:
            async with client.stream('GET','https://public-api.etoro.com/api/v1/market-data/instruments',
                params={'instrumentIds':'1'},headers={'x-api-key':cfg.api_key,'x-user-key':cfg.user_key,'x-request-id':str(uuid4())}) as response:
                result['http_status']=response.status_code
                if response.status_code!=200:
                    result['status']='provider_rejected'; return result
                payload=bytearray()
                async for chunk in response.aiter_bytes():
                    payload.extend(chunk)
                    if len(payload)>1_000_000:
                        result['status']='response_too_large'; return result
        if any(key.encode() in payload for key in (cfg.api_key,cfg.user_key)):
            result['status']='credential_material_discarded'; return result
        data=json.loads(payload)
        valid=isinstance(data,dict) and isinstance(data.get('instrumentDisplayDatas'),list)
        result['status']='authenticated_metadata_access' if valid else 'unexpected_schema'
    except (httpx.HTTPError,ValueError,TypeError): result['status']='probe_failed'
    return result

if __name__=='__main__':
    print(json.dumps(asyncio.run(verify()),indent=2))
