"""Explicit optional research-data adapters. No automatic provider or feed fallback.

Every response includes retrieval provenance. A provider's historical candle timestamp
is not proof of when its value was originally available: normalized bars conservatively
use retrieval time as availability unless the input includes a verified availability.
"""
from __future__ import annotations

import asyncio
import csv
import hashlib
import importlib.util
import io
import json
import math
import re
import zipfile
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Any, Protocol
from zoneinfo import ZoneInfo

import httpx

from selery_shared.models import Bar, Feed, Timeframe
from .providers import SECONDS, valid_symbol

UTC = timezone.utc
NY = ZoneInfo('America/New_York')
MAX_RESPONSE_BYTES = 20_000_000


class DataUnavailable(ValueError):
    """Sanitized operational error; never contains request URLs or credentials."""


@dataclass(frozen=True)
class DataBatch:
    provider: str
    dataset: str
    feed: Feed
    retrieved_at: datetime
    records: list[dict[str, Any]]
    source_url: str
    delay_seconds: int | None = None
    historical_availability_verified: bool = False
    limitations: tuple[str, ...] = ()
    version: str = '1'
    raw: bytes = field(default=b'', repr=False)

    def provenance(self) -> dict[str, Any]:
        return {'provider': self.provider, 'dataset': self.dataset, 'feed': str(self.feed),
                'retrieved_at': self.retrieved_at.isoformat(), 'available_at': self.retrieved_at.isoformat(),
                'delay_seconds': self.delay_seconds, 'historical_availability_verified': self.historical_availability_verified,
                'source_url': self.source_url, 'version': self.version, 'limitations': list(self.limitations),
                'raw_sha256': hashlib.sha256(self.raw).hexdigest()}


class ResearchAdapter(Protocol):
    def capabilities(self) -> dict[str, Any]: ...
    async def fetch(self, dataset: str, **query: Any) -> DataBatch: ...


def utc_now() -> datetime:
    return datetime.now(UTC)


def stamp(value: Any, tz=UTC) -> int:
    if isinstance(value, (int, float)):
        return int(value)
    parsed = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    return int(parsed.replace(tzinfo=tz).timestamp() if parsed.tzinfo is None else parsed.timestamp())


def bars_from_batch(batch: DataBatch, symbol: str, timeframe: Timeframe) -> list[Bar]:
    valid_symbol(symbol)
    now = int(batch.retrieved_at.timestamp())
    bars = []
    seen: set[int] = set()
    for row in batch.records:
        ts = int(row['time'])
        if ts in seen:
            raise DataUnavailable('Duplicate bar timestamps require source reconciliation')
        seen.add(ts)
        values = [float(row[k]) for k in ('open', 'high', 'low', 'close', 'volume')]
        o, h, l, c, v = values
        if not all(math.isfinite(x) for x in values) or min(o, h, l, c) <= 0 or v < 0 or not l <= min(o, c) <= max(o, c) <= h:
            raise DataUnavailable('Invalid OHLCV data')
        end = ts + SECONDS[timeframe]
        if timeframe == Timeframe.D1:
            # Full next local midnight is conservative for regular and extended sessions, including DST.
            day = datetime.fromtimestamp(ts, NY).date()
            end = max(end, int(datetime.combine(day + timedelta(days=1), datetime.min.time(), NY).timestamp()))
        available = int(row['available_at']) if batch.historical_availability_verified and 'available_at' in row else max(now, end)
        if available < end:
            raise DataUnavailable('Bar availability precedes interval completion')
        bars.append(Bar(symbol=symbol, time=ts, available_at=available, open=o, high=h, low=l, close=c,
                        volume=v, feed=batch.feed, finalized=end <= now and available <= now))
    return sorted(bars, key=lambda bar: bar.time)


class HttpAdapter:
    name = ''
    host = ''
    datasets: tuple[str, ...] = ()
    docs = ''
    paid = False

    def __init__(self, key: str = '', *, transport: httpx.AsyncBaseTransport | None = None,
                 clock=utc_now, entitled=False):
        self._key = key
        self._transport = transport
        self.clock = clock
        self.entitled = entitled

    def capabilities(self):
        configured = bool(self._key) and (not self.paid or self.entitled)
        return {'provider': self.name, 'configured': configured, 'datasets': list(self.datasets),
                'feed': 'delayed', 'delay_seconds': None, 'consolidated_volume_verified': False,
                'reason': None if configured else ('Key and explicit paid entitlement required' if self.paid else 'API key required'),
                'docs': self.docs, 'automatic_fallback': False}

    def require(self, dataset):
        if dataset not in self.datasets:
            raise DataUnavailable(f'{self.name}: unsupported dataset')
        if not self.capabilities()['configured']:
            raise DataUnavailable(f'{self.name}: {self.capabilities()["reason"]}')

    async def get(self, path, *, params=None, headers=None) -> tuple[Any, bytes]:
        # Each concrete adapter constructs its fixed path; callers never supply a URL.
        if not path.startswith('/') or path.startswith('//') or '?' in path or '..' in path:
            raise DataUnavailable('Invalid data path')
        try:
            async with httpx.AsyncClient(base_url=f'https://{self.host}', transport=self._transport,
                                        timeout=20, follow_redirects=False) as client:
                async with client.stream('GET', path, params=params, headers=headers) as response:
                    if response.status_code != 200:
                        raise DataUnavailable(f'{self.name}: data unavailable (HTTP {response.status_code})')
                    chunks, size = [], 0
                    async for chunk in response.aiter_bytes():
                        size += len(chunk)
                        if size > MAX_RESPONSE_BYTES:
                            raise DataUnavailable(f'{self.name}: response exceeds size limit')
                        chunks.append(chunk)
                    raw = b''.join(chunks)
        except httpx.HTTPError:
            raise DataUnavailable(f'{self.name}: connection unavailable') from None
        # Provider error payloads can echo query credentials. Refuse rather than archive them.
        if self._key and self._key.encode() in raw:
            raise DataUnavailable(f'{self.name}: response unexpectedly contains credential material')
        try:
            return json.loads(raw), raw
        except (ValueError, UnicodeDecodeError):
            return None, raw

    def batch(self, dataset, records, raw, *, feed=Feed.DELAYED, limitations=()):
        return DataBatch(self.name, dataset, feed, self.clock(), records, self.docs, raw=raw,
                         limitations=('Feed delay and original historical availability are unverified.', *limitations))


class FinnhubAdapter(HttpAdapter):
    name, host = 'finnhub', 'finnhub.io'
    datasets = ('quote', 'candles')
    docs = 'https://finnhub.io/docs/api/quote'

    async def fetch(self, dataset, **query):
        self.require(dataset)
        symbol = valid_symbol(query['symbol'])
        headers = {'X-Finnhub-Token': self._key}
        if dataset == 'quote':
            payload, raw = await self.get('/api/v1/quote', params={'symbol': symbol}, headers=headers)
            if not isinstance(payload, dict) or not payload.get('t') or not payload.get('c'):
                raise DataUnavailable('finnhub: no timestamped quote available')
            return self.batch(dataset, [{'symbol': symbol, 'price': payload['c'], 'time': payload['t'],
                                         'previous_close': payload.get('pc')}], raw)
        start, end = query_range(query)
        resolution = {Timeframe.M5: '5', Timeframe.H1: '60', Timeframe.D1: 'D'}.get(query.get('timeframe', Timeframe.D1))
        if resolution is None:
            raise DataUnavailable('finnhub: unsupported candle interval')
        payload, raw = await self.get('/api/v1/stock/candle', params={'symbol': symbol, 'resolution': resolution,
                                     'from': int(start.timestamp()), 'to': int(end.timestamp())}, headers=headers)
        if not isinstance(payload, dict) or payload.get('s') != 'ok':
            raise DataUnavailable('finnhub: candles unavailable; verify plan entitlement')
        keys = ['t', 'o', 'h', 'l', 'c', 'v']
        if len({len(payload[k]) for k in keys}) != 1:
            raise DataUnavailable('finnhub: misaligned candle arrays')
        rows = [dict(zip(['time', 'open', 'high', 'low', 'close', 'volume'], values)) for values in zip(*(payload[k] for k in keys))]
        return self.batch(dataset, rows, raw, limitations=('Candle entitlement may require a paid plan.',))


class AlphaVantageAdapter(HttpAdapter):
    name, host = 'alpha_vantage', 'www.alphavantage.co'
    datasets = ('daily_bars',)
    docs = 'https://www.alphavantage.co/documentation/'

    async def fetch(self, dataset, **query):
        self.require(dataset)
        symbol = valid_symbol(query['symbol'])
        payload, raw = await self.get('/query', params={'function': 'TIME_SERIES_DAILY', 'symbol': symbol,
                                                       'outputsize': 'compact', 'apikey': self._key})
        series = payload.get('Time Series (Daily)') if isinstance(payload, dict) else None
        if series is None:
            raise DataUnavailable('alpha_vantage: daily series unavailable or quota exhausted')
        rows = [{'time': stamp(day, NY), 'open': row['1. open'], 'high': row['2. high'], 'low': row['3. low'],
                 'close': row['4. close'], 'volume': row['5. volume']} for day, row in series.items()]
        return self.batch(dataset, rows, raw, limitations=('Raw daily prices; compact response is at most 100 observations.',))


class TwelveDataAdapter(HttpAdapter):
    name, host = 'twelve_data', 'api.twelvedata.com'
    datasets = ('candles',)
    docs = 'https://twelvedata.com/docs'

    async def fetch(self, dataset, **query):
        self.require(dataset)
        interval = {Timeframe.M5: '5min', Timeframe.H1: '1h', Timeframe.D1: '1day'}.get(query.get('timeframe', Timeframe.D1))
        if interval is None:
            raise DataUnavailable('twelve_data: unsupported candle interval')
        payload, raw = await self.get('/time_series', params={'symbol': valid_symbol(query['symbol']), 'interval': interval,
                                     'timezone': 'UTC', 'outputsize': 500, 'apikey': self._key, 'adjust': 'none'})
        if not isinstance(payload, dict) or payload.get('status') != 'ok':
            raise DataUnavailable('twelve_data: series unavailable or entitlement missing')
        rows = [{'time': stamp(row['datetime'], NY if interval == '1day' else UTC),
                 **{field: row.get(field, 0) for field in ('open', 'high', 'low', 'close', 'volume')}} for row in payload['values']]
        return self.batch(dataset, rows, raw, limitations=('Volume coverage has not been verified as consolidated.',))


class FredAdapter(HttpAdapter):
    name, host = 'fred', 'api.stlouisfed.org'
    datasets = ('observations',)
    docs = 'https://fred.stlouisfed.org/docs/api/fred/series_observations.html'

    async def fetch(self, dataset, **query):
        self.require(dataset)
        series = query['series_id']
        if not re.fullmatch(r'[A-Za-z0-9_]{1,80}', series):
            raise DataUnavailable('fred: invalid series identifier')
        as_of = date.fromisoformat(str(query['as_of']))
        if as_of > self.clock().date():
            raise DataUnavailable('fred: future vintage is unavailable')
        payload, raw = await self.get('/fred/series/observations', params={'series_id': series, 'api_key': self._key,
                                     'file_type': 'json', 'realtime_start': str(as_of), 'realtime_end': str(as_of),
                                     'sort_order': 'asc', 'limit': 10000})
        if not isinstance(payload, dict) or 'observations' not in payload:
            raise DataUnavailable('fred: observations unavailable')
        rows = []
        for row in payload['observations']:
            rows.append({'date': row['date'], 'value': None if row['value'] == '.' else float(row['value']),
                         'vintage_start': row['realtime_start'], 'vintage_end': row['realtime_end'], 'as_of': str(as_of)})
        return self.batch(dataset, rows, raw, limitations=('Vintage is date-level; release time must be verified before intraday use.',))


class SecAdapter(HttpAdapter):
    name, host = 'sec', 'data.sec.gov'
    datasets = ('submissions', 'companyfacts')
    docs = 'https://www.sec.gov/search-filings/edgar-application-programming-interfaces'

    def __init__(self, user_agent='', **kwargs):
        super().__init__('', **kwargs)
        self.user_agent = user_agent

    def capabilities(self):
        valid = bool(re.fullmatch(r'[^\r\n]{3,120} [^\s@]+@[^\s@]+\.[^\s@]+', self.user_agent))
        return {'provider': self.name, 'configured': valid, 'datasets': list(self.datasets), 'docs': self.docs,
                'reason': None if valid else 'SEC_USER_AGENT must identify an application and contact email',
                'automatic_fallback': False, 'historical_availability_verified': False}

    async def fetch(self, dataset, **query):
        self.require(dataset)
        cik = str(query['cik'])
        if not re.fullmatch(r'\d{1,10}', cik):
            raise DataUnavailable('sec: invalid CIK')
        path = f'/submissions/CIK{cik.zfill(10)}.json' if dataset == 'submissions' else f'/api/xbrl/companyfacts/CIK{cik.zfill(10)}.json'
        payload, raw = await self.get(path, headers={'User-Agent': self.user_agent})
        if not isinstance(payload, dict):
            raise DataUnavailable('sec: invalid response')
        return self.batch(dataset, [payload], raw, limitations=('Use filing acceptance timestamps, not reporting period end, for point-in-time analysis.',))


class FrenchAdapter(HttpAdapter):
    name, host = 'ken_french', 'mba.tuck.dartmouth.edu'
    datasets = ('daily_three_factors',)
    docs = 'https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html'

    def capabilities(self):
        return {'provider': self.name, 'configured': True, 'datasets': list(self.datasets), 'docs': self.docs,
                'reason': None, 'automatic_fallback': False, 'historical_availability_verified': False}

    async def fetch(self, dataset, **query):
        self.require(dataset)
        _, raw = await self.get('/pages/faculty/ken.french/ftp/F-F_Research_Data_Factors_daily_CSV.zip')
        try:
            with zipfile.ZipFile(io.BytesIO(raw)) as archive:
                entries = [item for item in archive.infolist() if item.filename.lower().endswith('.csv')]
                if len(entries) != 1 or entries[0].file_size > MAX_RESPONSE_BYTES:
                    raise DataUnavailable('ken_french: unexpected archive size or members')
                content = archive.read(entries[0]).decode('utf-8-sig')
            rows = []
            for row in csv.reader(io.StringIO(content)):
                if len(row) >= 5 and re.fullmatch(r'\d{8}', row[0].strip()):
                    rows.append({'date': datetime.strptime(row[0].strip(), '%Y%m%d').date().isoformat(),
                                 **{key: float(value) for key, value in zip(('market_minus_rf_percent', 'smb_percent', 'hml_percent', 'rf_percent'), row[1:5])}})
        except (zipfile.BadZipFile, ValueError, UnicodeDecodeError):
            raise DataUnavailable('ken_french: invalid factor archive') from None
        return self.batch(dataset, rows, raw, limitations=('Factors are published percentage returns; historical vintage unavailable, so do not use as historical live features.',))


class MassiveAdapter(HttpAdapter):
    name, host = 'massive', 'api.massive.com'
    datasets, paid = ('candles',), True
    docs = 'https://massive.com/docs/rest/stocks/aggregates/custom-bars'

    async def fetch(self, dataset, **query):
        self.require(dataset)
        start, end = query_range(query)
        multiplier, span = {Timeframe.M5: (5, 'minute'), Timeframe.H1: (1, 'hour'), Timeframe.D1: (1, 'day')}.get(query.get('timeframe', Timeframe.D1), (None, None))
        if multiplier is None:
            raise DataUnavailable('massive: unsupported interval')
        path = f'/v2/aggs/ticker/{valid_symbol(query["symbol"])}/range/{multiplier}/{span}/{start.date()}/{end.date()}'
        payload, raw = await self.get(path, params={'adjusted': 'false', 'sort': 'asc', 'limit': 5000}, headers={'Authorization': f'Bearer {self._key}'})
        if not isinstance(payload, dict) or payload.get('status') not in ('OK', 'DELAYED'):
            raise DataUnavailable('massive: data unavailable')
        if payload.get('next_url'):
            raise DataUnavailable('massive: range exceeds one page; choose a smaller explicit range')
        rows = [{'time': row['t'] // 1000, 'open': row['o'], 'high': row['h'], 'low': row['l'], 'close': row['c'], 'volume': row['v']} for row in payload.get('results', [])]
        return self.batch(dataset, rows, raw, limitations=('Paid entitlement explicitly required; consolidated coverage must be independently verified.',))


class YFinanceAdapter:
    """Optional SDK adapter; personal-use historical research, with no fallback."""
    def __init__(self, *, enabled=False, clock=utc_now, loader=None):
        self.enabled, self.clock, self.loader = enabled, clock, loader

    def capabilities(self):
        installed = self.loader is not None or importlib.util.find_spec('yfinance') is not None
        return {'provider': 'yfinance', 'configured': self.enabled and installed, 'datasets': ['daily_bars'],
                'reason': None if self.enabled and installed else 'Explicit enablement and optional yfinance package required',
                'docs': 'https://ranaroussi.github.io/yfinance/', 'feed': 'delayed', 'delay_seconds': None,
                'automatic_fallback': False, 'consolidated_volume_verified': False}

    async def fetch(self, dataset, **query):
        if dataset != 'daily_bars' or not self.capabilities()['configured']:
            raise DataUnavailable('yfinance: optional daily research adapter is unavailable')
        start, end = query_range(query)
        symbol = valid_symbol(query['symbol'])
        def read():
            if self.loader:
                return self.loader(symbol, start, end)
            import yfinance as yf
            return yf.Ticker(symbol).history(start=start.date(), end=end.date(), interval='1d', auto_adjust=False,
                                            back_adjust=False, actions=False, raise_errors=True)
        try:
            frame = await asyncio.to_thread(read)
            rows = [{'time': int(index.timestamp()), **{key.lower(): float(row[key]) for key in ('Open', 'High', 'Low', 'Close', 'Volume')}} for index, row in frame.iterrows()]
        except Exception:
            raise DataUnavailable('yfinance: research data unavailable') from None
        raw = json.dumps(rows, allow_nan=False, separators=(',', ':')).encode()
        return DataBatch('yfinance', dataset, Feed.DELAYED, self.clock(), rows, 'https://ranaroussi.github.io/yfinance/', raw=raw,
                         limitations=('Personal-use unofficial data access; SDK-normalized archive, raw HTTP payload unavailable.',
                                      'Historical availability and feed delay unverified; no automatic substitution.'))


class DatabentoAdapter:
    """Paid historical bars only; requires explicit dataset and enablement, never runs on startup."""
    def __init__(self, key='', *, dataset='', entitled=False, clock=utc_now, loader=None):
        self._key, self.dataset, self.entitled = key, dataset, entitled
        self.clock, self.loader = clock, loader

    def capabilities(self):
        installed = self.loader is not None or importlib.util.find_spec('databento') is not None
        valid = bool(self._key and self.entitled and re.fullmatch(r'[A-Z0-9]+\.[A-Z0-9]+', self.dataset) and installed)
        return {'provider': 'databento', 'configured': valid, 'datasets': ['daily_bars'], 'feed': 'delayed',
                'reason': None if valid else 'API key, paid enablement, explicit dataset and optional SDK required',
                'docs': 'https://databento.com/docs/api-reference-historical/timeseries/timeseries-get-range',
                'automatic_fallback': False, 'consolidated_volume_verified': False}

    async def fetch(self, dataset, **query):
        if dataset != 'daily_bars' or not self.capabilities()['configured']:
            raise DataUnavailable('databento: paid adapter is not configured')
        start, end = query_range(query)
        symbol = valid_symbol(query['symbol'])
        def read():
            if self.loader:
                return self.loader(symbol, start, end, self.dataset)
            import databento as db
            return db.Historical(self._key).timeseries.get_range(dataset=self.dataset, symbols=[symbol],
                       schema='ohlcv-1d', start=start.isoformat(), end=end.isoformat()).to_df()
        try:
            frame = await asyncio.to_thread(read)
            rows = [{'time': int(index.timestamp()), **{key: float(row[key]) for key in ('open', 'high', 'low', 'close', 'volume')}} for index, row in frame.iterrows()]
        except Exception:
            raise DataUnavailable('databento: historical bars unavailable') from None
        raw = json.dumps(rows, allow_nan=False, separators=(',', ':')).encode()
        return DataBatch('databento', self.dataset, Feed.DELAYED, self.clock(), rows, self.capabilities()['docs'], raw=raw,
                         limitations=('Manual paid data request; SDK-normalized archival payload.', 'Coverage depends on the selected dataset; this adapter does not assert SIP consolidation.'))


def query_range(query):
    start = datetime.fromisoformat(str(query['start']).replace('Z', '+00:00'))
    end = datetime.fromisoformat(str(query['end']).replace('Z', '+00:00'))
    if start.tzinfo is None or end.tzinfo is None or start >= end or end - start > timedelta(days=366):
        raise DataUnavailable('Use an explicit timezone-aware interval of at most 366 days')
    return start, end


def provider_catalog(config: dict[str, str] | None = None):
    """Inspect configuration only. Never probe an account or spend on data requests."""
    config = config or {}
    adapters = [FinnhubAdapter(config.get('FINNHUB_API_KEY', '')), AlphaVantageAdapter(config.get('ALPHA_VANTAGE_API_KEY', '')),
                TwelveDataAdapter(config.get('TWELVE_DATA_API_KEY', '')), FredAdapter(config.get('FRED_API_KEY', '')),
                SecAdapter(config.get('SEC_USER_AGENT', '')), FrenchAdapter(), YFinanceAdapter(), MassiveAdapter(), DatabentoAdapter(), AlpacaHistoricalSIPAdapter()]
    return [adapter.capabilities() for adapter in adapters]


class AlpacaHistoricalSIPAdapter:
    """Historical SIP is separate from forward IEX and requires an explicit entitlement check."""
    def __init__(self, config=None, *, entitlement_verified=False, provider=None, clock=utc_now):
        self.clock, self.config, self.entitlement_verified = clock, config, entitlement_verified
        self.provider = provider
        if config is not None:
            from urllib.parse import urlparse
            parsed = urlparse(config.endpoint)
            if parsed.scheme != 'https' or parsed.netloc != 'paper-api.alpaca.markets':
                raise DataUnavailable('Alpaca configuration must use the HTTPS paper host')

    def capabilities(self):
        configured = bool(self.config and self.config.key and self.config.secret and self.entitlement_verified)
        return {'provider': 'alpaca_historical_sip', 'configured': configured, 'datasets': ['candles'], 'feed': 'sip',
                'delay_seconds': 900, 'consolidated_volume_verified': configured, 'automatic_fallback': False,
                'reason': None if configured else 'Alpaca credentials and verified historical SIP entitlement required',
                'docs': 'https://docs.alpaca.markets/us/docs/market-data-faq',
                'forward_comparison': 'Historical SIP is incompatible with the default IEX forward feed.'}

    async def fetch(self, dataset, **query):
        if dataset != 'candles' or not self.capabilities()['configured']:
            raise DataUnavailable('alpaca_historical_sip: entitlement is not verified')
        from .providers import AlpacaProvider, TF_MAP
        start, end = query_range(query)
        if end > self.clock() - timedelta(minutes=16):
            raise DataUnavailable('Historical SIP requests must end at least 16 minutes before now')
        symbol = valid_symbol(query['symbol'])
        timeframe = Timeframe(query.get('timeframe', Timeframe.D1))
        owned = self.provider is None
        provider = self.provider or AlpacaProvider(self.config)
        try:
            payload = await provider.get(f'/v2/stocks/{symbol}/bars', {'feed': 'sip', 'timeframe': TF_MAP[timeframe],
                'start': start.isoformat(), 'end': end.isoformat(), 'adjustment': 'raw', 'limit': 10000, 'sort': 'asc'})
        finally:
            if owned:
                await provider.client.aclose()
        if payload.get('next_page_token'):
            raise DataUnavailable('Historical SIP range exceeds one page; choose a smaller explicit range')
        rows = [{'time': stamp(row['t']), 'open': row['o'], 'high': row['h'], 'low': row['l'],
                 'close': row['c'], 'volume': row['v']} for row in payload.get('bars', [])]
        raw = json.dumps(payload, sort_keys=True, separators=(',', ':')).encode()
        return DataBatch('alpaca', 'historical_sip', Feed.SIP, self.clock(), rows, self.capabilities()['docs'],
                         delay_seconds=900, raw=raw, limitations=('Historical SIP cannot be compared directly with the IEX forward feed.',
                         'Historical dissemination timestamps are unverified; archival retrieval time is conservative availability.'))
