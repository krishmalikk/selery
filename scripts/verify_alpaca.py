"""Explicit read-only credential/feed audit. Never emits credentials or account data."""
import hashlib
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen
from urllib.error import HTTPError

ROOT = Path(__file__).resolve().parents[1]

def run():
    values = {}
    for line in (ROOT / '.env').read_text().splitlines():
        if '=' in line and not line.lstrip().startswith('#'):
            key, value = line.removeprefix('export ').split('=', 1)
            values[key.strip()] = value.strip().strip('\"\'')
    endpoint = urlparse(values.get('ALPACA_ENDPOINT', ''))
    if endpoint.scheme != 'https' or endpoint.hostname != 'paper-api.alpaca.markets' or endpoint.username or endpoint.password or endpoint.port:
        raise SystemExit('REFUSED: ALPACA_ENDPOINT must be the HTTPS paper host.')
    headers = {'APCA-API-KEY-ID': values['ALPACA_KEY'], 'APCA-API-SECRET-KEY': values['ALPACA_SECRET']}
    report = {'checked_at': datetime.now(timezone.utc).isoformat(), 'endpoint': 'paper-api.alpaca.markets', 'checks': []}
    fixtures = ROOT / 'packages/fixtures'
    fixtures.mkdir(parents=True, exist_ok=True)
    end = datetime.now(timezone.utc) - timedelta(days=1)
    for feed in ['iex', 'sip']:
        for timeframe, days in [('1Min', 7), ('5Min', 14), ('1Hour', 60), ('1Day', 365)]:
            for symbol in ['SPY', 'QQQ', 'AAPL', 'NVDA'] if feed == 'iex' else ['SPY']:
                params = {'feed': feed, 'timeframe': timeframe, 'start': (end-timedelta(days=days)).isoformat(), 'end': end.isoformat(), 'limit': 2000, 'adjustment': 'raw', 'sort': 'desc'}
                req = Request('https://data.alpaca.markets/v2/stocks/'+symbol+'/bars?'+urlencode(params), headers=headers)
                try:
                    with urlopen(req, timeout=30) as response:
                        payload = json.load(response)
                    payload['bars'] = sorted(payload.get('bars', []), key=lambda x:x['t'])
                    captured = {'provenance': {'provider':'alpaca','feed':feed,'symbol':symbol,'timeframe':timeframe,'recorded_at':report['checked_at'],'synthetic':False,'adjustment':'raw','request':params}, 'payload':payload}
                    target = fixtures / f'{symbol}-{timeframe}-{feed}.json'
                    target.write_text(json.dumps(captured, indent=2)+'\n')
                    report['checks'].append({'symbol':symbol,'feed':feed,'timeframe':timeframe,'status':200,'bars':len(payload['bars']),'sha256':hashlib.sha256(target.read_bytes()).hexdigest()})
                except HTTPError as exc:
                    report['checks'].append({'symbol':symbol,'feed':feed,'timeframe':timeframe,'status':exc.code})
                    if exc.code in [401,403] and feed == 'iex':
                        break
    try:
        req = Request('https://data.alpaca.markets/v1beta1/news?symbols=SPY,QQQ,AAPL,NVDA&limit=20&include_content=false',headers=headers)
        with urlopen(req,timeout=30) as response:
            payload=json.load(response)
        (fixtures/'news.json').write_text(json.dumps({'provenance':{'provider':'alpaca','recorded_at':report['checked_at'],'synthetic':False},'payload':payload},indent=2)+'\n')
        report['checks'].append({'resource':'news','status':200,'count':len(payload.get('news',[]))})
    except HTTPError as exc:
        report['checks'].append({'resource':'news','status':exc.code})
    (ROOT/'docs/alpaca-verification.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))

if __name__ == '__main__':
    run()
