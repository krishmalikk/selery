"""Authorized public research observations. Never accesses the caller's broker state."""
from __future__ import annotations

import asyncio
import hashlib
import json
import math
import os
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone, date, timedelta
from pathlib import Path
from uuid import uuid4

import httpx
from fastapi import Depends, HTTPException, Query
from sqlalchemy import select, delete, insert, update, func
from selery_shared.models import (PublicSource, PublicTrader, PublicActivity, PublicTraderPage,
    PublicActivityPage, PublicActivityDetail, PublicRefreshRequest, PublicRefreshResult,
    Citation, ChatResponse, Timeframe, Feed)
from .storage import tables, serial

UTC = timezone.utc
USERNAME = re.compile(r'^[A-Za-z0-9_-]{1,80}$')
SYMBOL = re.compile(r'^[A-Z][A-Z0-9.\-]{0,11}$')
FIXTURE = Path(__file__).resolve().parents[3] / 'fixtures/public-traders/etoro.json'


@dataclass(frozen=True)
class PublicConfig:
    mode: str = 'live'
    api_key: str = field(default='', repr=False)
    user_key: str = field(default='', repr=False)
    data_allowed: bool = False
    llm_allowed: bool = False

    @classmethod
    def load(cls):
        mode = os.getenv('SELERY_PUBLIC_TRADERS_MODE', 'live')
        if mode not in ('live', 'fixtures'): raise ValueError('Invalid public traders mode')
        def credential(*names):
            values = {os.getenv(name, '').strip() for name in names} - {''}
            if len(values) > 1: raise ValueError('Conflicting eToro credential aliases: '+', '.join(names))
            return next(iter(values), '')
        return cls(mode, credential('ETORO_API_KEY','ETORO_PUBLIC_KEY'), credential('ETORO_USER_KEY','ETORO_PRIVATE_KEY'),
                   os.getenv('SELERY_ETORO_DATA_ALLOWED', 'false').lower() == 'true',
                   os.getenv('SELERY_ETORO_LLM_ALLOWED', 'false').lower() == 'true')

    @property
    def active(self): return bool(self.api_key and self.user_key and self.data_allowed)


class PublicUnavailable(ValueError):
    def __init__(self, message, status=0): super().__init__(message); self.status = status


def stamp(value):
    if not value: return None
    try:
        parsed = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        return parsed.astimezone(UTC) if parsed.tzinfo else None
    except ValueError: return None


def number(value, low=None, high=None):
    if isinstance(value, bool) or not isinstance(value, (int, float)): return None
    if not math.isfinite(value) or (low is not None and value < low) or (high is not None and value > high): return None
    return float(value)


class EtoroPublicAdapter:
    """Small GET-only allowlist, no generic proxy and no automatic retries."""
    def __init__(self, config, transport=None, spacing=1.1):
        self.config = config; self.transport = transport; self.spacing = spacing
        self.lock = asyncio.Lock(); self.next_request = 0.; self.blocked_until = 0.

    async def get(self, path, params=None):
        allowed = path in ('/api/v2/portfolios/rankings', '/api/v1/market-data/instruments')
        allowed |= bool(re.fullmatch(r'/api/v1/user-info/people/[A-Za-z0-9_-]{1,80}/portfolio/live', path))
        if not allowed: raise PublicUnavailable('Public-data operation is not allowlisted')
        if not self.config.active: raise PublicUnavailable('eToro credentials and data-use permission are required')
        async with self.lock:
            if time.monotonic() < self.blocked_until: raise PublicUnavailable('eToro rate limit cooldown is active', 429)
            await asyncio.sleep(max(0, self.next_request - time.monotonic()))
            self.next_request = time.monotonic() + self.spacing
            headers = {'x-api-key': self.config.api_key, 'x-user-key': self.config.user_key, 'x-request-id': str(uuid4())}
            try:
                async with httpx.AsyncClient(transport=self.transport, timeout=20, follow_redirects=False) as client:
                    async with client.stream('GET', 'https://public-api.etoro.com' + path, params=params, headers=headers) as response:
                        if response.status_code != 200:
                            if response.status_code == 429:
                                try: delay = float(response.headers.get('Retry-After', '60'))
                                except ValueError: delay = 60
                                self.blocked_until = time.monotonic() + (min(max(delay, 60), 3600) if math.isfinite(delay) else 60)
                            raise PublicUnavailable(f'eToro public data unavailable (HTTP {response.status_code}); no automatic retry.', response.status_code)
                        chunks = []; size = 0
                        async for chunk in response.aiter_bytes():
                            size += len(chunk)
                            if size > 4_000_000: raise PublicUnavailable('eToro response exceeds the bounded size')
                            chunks.append(chunk)
                raw = b''.join(chunks)
                if any(key and key.encode() in raw for key in (self.config.api_key, self.config.user_key)):
                    raise PublicUnavailable('Provider response contained credential material; discarded')
                result = json.loads(raw)
                if not isinstance(result, dict) or result.get('error'): raise PublicUnavailable('Invalid eToro public response')
                return result
            except (httpx.HTTPError, ValueError) as exc:
                if isinstance(exc, PublicUnavailable): raise
                raise PublicUnavailable('eToro public data response could not be read') from None

    async def directory(self, page):
        data = await self.get('/api/v2/portfolios/rankings', {'period':'CurrYear','page':page,'pageSize':20})
        if not isinstance(data.get('results'), list) or not isinstance(data.get('pagination'), dict):
            raise PublicUnavailable('eToro directory schema is unavailable')
        return data

    async def activity(self, username):
        if not USERNAME.fullmatch(username): raise PublicUnavailable('Invalid public username')
        data = await self.get(f'/api/v1/user-info/people/{username}/portfolio/live')
        if data.get('isPrivate') is True or data.get('isPublic') is False:
            raise PublicUnavailable('Public profile access was withdrawn', 403)
        if not isinstance(data.get('positions'), list): raise PublicUnavailable('eToro open-record schema is unavailable')
        # Direct public records only: nested copied allocations are not attributed to this trader.
        if len(data['positions']) > 1000: raise PublicUnavailable('Public snapshot exceeds record limit')
        ids = sorted({str(row['instrumentId']) for row in data['positions'] if isinstance(row, dict) and type(row.get('instrumentId')) is int})
        instruments = []
        for start in range(0, len(ids), 100):
            result = await self.get('/api/v1/market-data/instruments', {'instrumentIds':','.join(ids[start:start+100])})
            if not isinstance(result.get('instrumentDisplayDatas'), list): raise PublicUnavailable('Instrument mapping unavailable')
            instruments.extend(result['instrumentDisplayDatas'])
        return data, instruments


def normalize_trader(row, now, synthetic=False):
    if not isinstance(row, dict): return None
    username = row.get('username')
    if not isinstance(username, str) or not USERNAME.fullmatch(username) or row.get('type') != 'trader': return None
    return PublicTrader(id='etoro:'+username.lower(), source='etoro', username=username,
        display_name=str(row.get('fullName') or username)[:160], source_url=('https://api-portal.etoro.com/api-reference/users-info/get-user-live-portfolio' if synthetic else 'https://www.etoro.com/people/'+username),
        observed_at=now, stale=synthetic, synthetic=synthetic,
        statistics={key:value for key in ('riskScore','copiers') if (value:=number(row.get(key),0)) is not None},
        statistics_note='eToro riskScore (provider scale) and copiers (count). No normalized performance ranking is claimed.')


def normalize_activity(trader, data, instruments, now):
    mapped = {str(row.get('instrumentID')):row for row in instruments if isinstance(row, dict)}
    found = {}
    for row in data['positions']:
        if not isinstance(row, dict) or type(row.get('positionId')) is not int or type(row.get('instrumentId')) is not int:
            raise PublicUnavailable('Public record lacks a stable numeric identifier')
        record_id = str(row['positionId']); instrument = mapped.get(str(row['instrumentId']), {})
        symbol = instrument.get('symbolFull')
        if not isinstance(symbol,str) or not SYMBOL.fullmatch(symbol): symbol = None
        opened = stamp(row.get('openTimestamp'))
        if opened and opened > now: opened = None
        # Display metadata does not establish shares versus CFD for a particular user.
        activity = PublicActivity(id=trader.id+':'+record_id, trader_id=trader.id, source='etoro',
            source_record_id=record_id, source_url=trader.source_url, symbol=symbol,
            instrument_name=str(instrument.get('instrumentDisplayName') or f'Instrument {row["instrumentId"]}')[:200],
            instrument_kind='unclassified', direction='long' if row.get('isBuy') is True else 'short' if row.get('isBuy') is False else 'unknown',
            opened_at=opened, first_observed_at=now, observed_at=now,
            entry_price=number(row.get('openRate'), 0.000000001), allocation_percent=number(row.get('investmentPct'),0,100),
            synthetic=trader.synthetic, stale=trader.synthetic,
            limitations=['Shares versus CFD and quote currency are unverified; no return comparison is calculated.',
                'Publication and broker synchronization times are unavailable.',
                'Snapshot polling can miss trades opened and closed between observations.',
                'Nested copied allocations are excluded. Exit price, quantity and motive are unavailable.'])
        if record_id in found and found[record_id] != activity: raise PublicUnavailable('Conflicting duplicate public records')
        found[record_id] = activity
    return list(found.values())


class PublicRegistry:
    def __init__(self, store, config=None, adapter=None):
        self.store = store; self.override = config; self.adapter = adapter; self.refresh_lock = asyncio.Lock()
        self.last_refresh = 0.

    @property
    def config(self): return self.override or PublicConfig.load()

    def sources(self):
        cfg = self.config; state = self.store.get('settings','public-etoro-status') or {}
        self.enabled()
        if cfg.mode == 'fixtures': status,reason = 'fixtures','Synthetic demonstration records; not real traders or verified provider access.'
        elif not cfg.active:
            status = 'pending'
            reason = ('Credentials loaded; public-record storage/display permission remains pending. Set SELERY_ETORO_DATA_ALLOWED=true only after confirming permitted use.'
                if cfg.api_key and cfg.user_key else 'Set ETORO_API_KEY (or ETORO_PUBLIC_KEY), ETORO_USER_KEY (or ETORO_PRIVATE_KEY) and confirm permitted data use.')
        else: status,reason = ('error',state['error']) if state.get('error') else ('configured','Configured; live provider and both-client acceptance are not yet certified.')
        return [PublicSource(id='etoro',name='eToro',status=status,reason=reason,can_refresh=cfg.mode=='fixtures' or cfg.active,
                    llm_allowed=cfg.mode=='live' and cfg.active and cfg.llm_allowed,last_checked_at=state.get('checked_at')),
            PublicSource(id='kinfo',name='Kinfo',status='pending',reason='Approved API/feed agreement required; scraping is prohibited. Inquiry draft is ready.'),
            PublicSource(id='afterhour',name='AfterHour',status='pending',reason='Authorized public-activity access is unverified. Inquiry draft is ready.')]

    def visible_clause(self, table):
        cfg = self.config
        return (table.c.payload['source'].as_string()=='etoro') & (table.c.payload['synthetic'].as_boolean()==(cfg.mode=='fixtures'))

    def enabled(self):
        enabled = self.config.mode=='fixtures' or self.config.active
        if not enabled: self.purge()
        return enabled

    def page(self, collection, model, limit, offset, source=None, q='', trader_id=None, symbol=None, date_from=None, date_to=None):
        if not self.enabled(): return {'items':[], 'total':0,'limit':limit,'offset':offset}
        table = tables[collection]; conditions = [self.visible_clause(table)]
        if source: conditions.append(table.c.payload['source'].as_string()==source)
        if collection == 'public_traders': conditions.append(table.c.payload['access'].as_string()=='public')
        else: conditions.append(table.c.payload['status'].as_string()!='access_unavailable')
        if trader_id: conditions.append(table.c.payload['trader_id'].as_string()==trader_id)
        if symbol: conditions.append(table.c.payload['symbol'].as_string()==symbol.upper())
        if q:
            escaped = q.lower().replace('\\','\\\\').replace('%','\\%').replace('_','\\_')
            fields = ('display_name','username') if collection=='public_traders' else ('symbol','instrument_name','trader_id')
            from sqlalchemy import or_
            conditions.append(or_(*(func.lower(table.c.payload[f].as_string()).like('%'+escaped+'%',escape='\\') for f in fields)))
        if date_from: conditions.append(table.c.payload['opened_at'].as_string()>=date_from.isoformat())
        if date_to: conditions.append(table.c.payload['opened_at'].as_string()<(date_to+timedelta(days=1)).isoformat())
        with self.store.engine.connect() as conn:
            total = conn.scalar(select(func.count()).select_from(table).where(*conditions))
            rows = conn.execute(select(table.c.payload).where(*conditions).order_by(table.c.payload['observed_at'].as_string().desc(),table.c.id).offset(offset).limit(limit))
            items = [self.fresh(model.model_validate(row[0])) for row in rows]
        return {'items':items,'total':total,'limit':limit,'offset':offset}

    def fresh(self, record):
        state = self.store.get('settings','public-etoro-status') or {}
        return record.model_copy(update={'stale':record.synthetic or bool(state.get('error')) or (datetime.now(UTC)-record.observed_at).total_seconds()>300})

    def activity(self, id):
        if not self.enabled(): raise HTTPException(404,'Public activity is unavailable')
        raw = self.store.get('public_activity',id)
        if not raw or raw['source']!='etoro' or raw['synthetic']!=(self.config.mode=='fixtures') or raw['status']=='access_unavailable':
            raise HTTPException(404,'Public activity is unavailable')
        activity = self.fresh(PublicActivity.model_validate(raw))
        trader = self.store.get('public_traders',activity.trader_id)
        if not trader or trader.get('access')!='public': raise HTTPException(404,'Public trader is unavailable')
        return activity, self.fresh(PublicTrader.model_validate(trader))

    def purge(self, trader_id=None):
        # Privacy withdrawal removes current and historical payloads, not merely hides them.
        with self.store.engine.begin() as conn:
            for name in ('public_activity','public_revisions','public_traders'):
                table = tables[name]
                condition = table.c.id==trader_id if name=='public_traders' else table.c.payload['trader_id'].as_string()==trader_id
                conn.execute(delete(table).where(condition if trader_id else table.c.payload['source'].as_string()=='etoro'))

    def save_snapshot(self, trader, records, observed_at=None):
        observed_at = observed_at or trader.observed_at
        table = tables['public_activity']; revisions = tables['public_revisions']
        with self.store.engine.begin() as conn:
            previous = {r[0]:r[1] for r in conn.execute(select(table.c.id,table.c.payload).where(table.c.payload['trader_id'].as_string()==trader.id))}
            incoming = {r.id:r for r in records}
            for id,old in previous.items():
                if id not in incoming:
                    incoming[id] = PublicActivity.model_validate(old).model_copy(update={'status':'no_longer_observed','observed_at':observed_at})
            for id,item in incoming.items():
                old = previous.get(id)
                if old:
                    item = item.model_copy(update={'first_observed_at':stamp(old['first_observed_at']), 'revision':old['revision']})
                    ignored = {'observed_at','stale','revision'}
                    if {k:v for k,v in serial(item).items() if k not in ignored}!={k:v for k,v in old.items() if k not in ignored}:
                        revision_id = id+':v'+str(old['revision'])
                        if conn.scalar(select(revisions.c.id).where(revisions.c.id==revision_id)) is None:
                            conn.execute(insert(revisions).values(id=revision_id,created_at=trader.observed_at,payload=old))
                        item = item.model_copy(update={'revision':old['revision']+1})
                    conn.execute(update(table).where(table.c.id==id).values(payload=serial(item)))
                else: conn.execute(insert(table).values(id=id,created_at=trader.observed_at,payload=serial(item)))
            traders = tables['public_traders']
            if conn.scalar(select(traders.c.id).where(traders.c.id==trader.id)):
                conn.execute(update(traders).where(traders.c.id==trader.id).values(payload=serial(trader)))
            else: conn.execute(insert(traders).values(id=trader.id,created_at=trader.observed_at,payload=serial(trader)))

    async def refresh(self, trader_id=None):
        if self.refresh_lock.locked(): raise HTTPException(409,'Public refresh already running')
        if time.monotonic()-self.last_refresh<5: raise HTTPException(429,'Wait five seconds before refreshing again')
        async with self.refresh_lock:
            self.last_refresh = time.monotonic(); cfg = self.config; now = datetime.now(UTC)
            if cfg.mode == 'fixtures':
                envelope = json.loads(FIXTURE.read_text())
                payload = envelope['data']
                if hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(',',':')).encode()).hexdigest()!=envelope['sha256']:
                    raise ValueError('Public fixture checksum mismatch')
                for row in payload['directory']['results']:
                    trader = normalize_trader(row,now,True)
                    if trader:
                        self.save_snapshot(trader,normalize_activity(trader,payload['snapshots'][trader.username],payload['instruments'],now))
                return PublicRefreshResult(updated=len(payload['directory']['results']),message='Loaded synthetic public-trader examples. No provider request or access verification occurred.')
            if not cfg.active:
                self.purge()
                raise HTTPException(422,'eToro credentials and permitted data use are required')
            if self.adapter is None or self.adapter.config != cfg: self.adapter = EtoroPublicAdapter(cfg)
            try:
                if trader_id:
                    raw = self.store.get('public_traders',trader_id)
                    if not raw or raw['source']!='etoro' or raw['synthetic']: raise HTTPException(404,'Public trader not found')
                    trader = PublicTrader.model_validate(raw)
                    data,instruments = await self.adapter.activity(trader.username)
                    records = normalize_activity(trader,data,instruments,now)
                    self.save_snapshot(trader,records,now); count = len(records)
                    message = 'Public snapshot refreshed. Missing records are not confirmed sales.'
                else:
                    state = self.store.get('settings','public-etoro-directory') or {'page':1}
                    data = await self.adapter.directory(state['page']); count = 0
                    for row in data['results']:
                        trader = normalize_trader(row,now)
                        if trader: self.store.put('public_traders',trader,trader.id); count += 1
                    self.store.put('settings',{'page':state['page']+1 if data['pagination'].get('hasNext') else 1},'public-etoro-directory')
                    message = 'Imported one directory page. Select a trader and refresh their activity. Coverage is limited to imported pages.'
                self.store.put('settings',{'checked_at':now.isoformat()},'public-etoro-status')
                return PublicRefreshResult(updated=count,message=message)
            except PublicUnavailable as exc:
                if exc.status in (401,403): self.purge() # Conservative when token/public access is withdrawn.
                elif exc.status==404 and trader_id: self.purge(trader_id)
                self.store.put('settings',{'checked_at':now.isoformat(),'error':str(exc)},'public-etoro-status')
                raise HTTPException(503,str(exc)) from None


def register_routes(app, authorized, get_chart):
    def registry(): return app.state.public_registry

    @app.get('/api/v1/public-traders/sources', response_model=list[PublicSource], dependencies=[Depends(authorized)])
    def sources(): return registry().sources()

    @app.get('/api/v1/public-traders',response_model=PublicTraderPage,dependencies=[Depends(authorized)])
    def traders(source:str|None=Query(None,pattern='^(etoro|kinfo|afterhour)$'),q:str=Query('',max_length=120),limit:int=Query(20,ge=1,le=100),offset:int=Query(0,ge=0)):
        return registry().page('public_traders',PublicTrader,limit,offset,source,q)

    @app.get('/api/v1/public-traders/activity',response_model=PublicActivityPage,dependencies=[Depends(authorized)])
    def activity(source:str|None=Query(None,pattern='^(etoro|kinfo|afterhour)$'),q:str=Query('',max_length=120),trader_id:str|None=None,symbol:str|None=None,date_from:date|None=None,date_to:date|None=None,limit:int=Query(20,ge=1,le=100),offset:int=Query(0,ge=0)):
        if date_from and date_to and date_from>date_to: raise HTTPException(422,'Date range is reversed')
        return registry().page('public_activity',PublicActivity,limit,offset,source,q,trader_id,symbol,date_from,date_to)

    async def detail_for(id,include_chart=True):
        activity,trader = registry().activity(id)
        chart = None
        reason = 'Market chart unavailable: the source instrument has not been mapped to a supported symbol.'
        if activity.symbol and include_chart:
            try:
                chart = await get_chart(activity.symbol,Timeframe.D1,Feed.IEX,200)
                reason = 'IEX only reference chart. Shares/CFD, currency and execution venue are unverified; no profit or return comparison is inferred. Chart may not cover the reported entry date.'
            except (ValueError,httpx.HTTPError,HTTPException): reason = 'Market context unavailable; public activity remains available.'
        current,trader = registry().activity(id)
        if current.revision != activity.revision:
            chart = None; reason = 'Public record changed during loading; reload for updated market context.'
        return PublicActivityDetail(activity=current,trader=trader,chart=chart,market_context_reason=reason,
            llm_allowed=registry().config.llm_allowed and not activity.synthetic and registry().config.active)

    @app.get('/api/v1/public-traders/activity/{id}',response_model=PublicActivityDetail,dependencies=[Depends(authorized)])
    async def detail(id:str,include_chart:bool=True): return await detail_for(id,include_chart)

    @app.post('/api/v1/public-traders/refresh',response_model=PublicRefreshResult,dependencies=[Depends(authorized)])
    async def refresh(body:PublicRefreshRequest): return await registry().refresh(body.trader_id)

    app.state.public_activity_detail = detail_for


async def activity_chat(app, body):
    if body.debate: raise HTTPException(422,'Public activity supports a single evidence response per request')
    registry = app.state.public_registry
    detail = await app.state.public_activity_detail(body.activity_id)
    item = detail.activity
    citations = [Citation(label='Public activity source',timestamp=item.observed_at,url=item.source_url,data_id=item.id)]
    if detail.chart and detail.chart.bars:
        bar = detail.chart.bars[-1]
        citations.append(Citation(label='IEX only market context · '+detail.chart.provenance.provider,
            timestamp=datetime.fromtimestamp(bar.available_at,UTC),
            url='https://docs.alpaca.markets/us/docs/market-data-faq',
            data_id=f'market:{detail.chart.symbol}:iex:{bar.time}'))
    summary = f'{detail.trader.display_name}: {item.instrument_name}, {item.direction}, status {item.status}. '
    summary += f'Observed by SELERY at {item.observed_at.isoformat()}. '
    summary += 'Exit, realized profit and motive are unavailable. A missing record does not prove a sale. '
    if item.synthetic: summary = 'SYNTHETIC EXAMPLE. '+summary
    from .assistant import BoundedAssistant,LlmConfig
    llm = LlmConfig.load()
    if detail.llm_allowed and llm.active(app.state.config.llm_cap):
        context = {'public_activity':item.model_dump(mode='json'),'trader':detail.trader.model_dump(mode='json'),
            'limitations':detail.market_context_reason,'citations':[c.model_dump(mode='json') for c in citations],
            'latest_reference_bar':detail.chart.bars[-1].model_dump(mode='json') if detail.chart and detail.chart.bars else None,
            'market_provenance':detail.chart.provenance.model_dump(mode='json') if detail.chart else None}
        # Re-check access immediately before sending evidence outside SELERY.
        registry.activity(item.id)
        if not registry.config.llm_allowed: raise HTTPException(422,'Public-data LLM permission was withdrawn')
        answer = await BoundedAssistant(app.state.store,llm,app.state.config.llm_cap).research(body,context,citations)
        registry.activity(item.id)
        if not registry.config.llm_allowed: raise HTTPException(422,'Public-data LLM permission was withdrawn')
        return answer
    return ChatResponse(message=summary+'Local record summary only; arbitrary questions require permitted LLM access.',citations=citations,mode='local')
