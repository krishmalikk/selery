from datetime import datetime, timedelta, timezone
import io
import zipfile

import httpx
import pytest

from selery_api.adapters import (AlphaVantageAdapter, DataBatch, DataUnavailable, DatabentoAdapter, FinnhubAdapter,
    FredAdapter, FrenchAdapter, MassiveAdapter, SecAdapter, TwelveDataAdapter, bars_from_batch, provider_catalog)
from selery_api.ingestion import RawArchive, ingest_batch, replay_bars
from selery_api.storage import Store
from selery_shared.models import Feed, Timeframe

NOW = datetime(2026, 9, 9, 20, tzinfo=timezone.utc)


def mock_json(payload, status=200, inspect=None):
    def handler(request):
        if inspect:
            inspect(request)
        return httpx.Response(status, json=payload)
    return httpx.MockTransport(handler)


@pytest.mark.asyncio
async def test_alpha_request_is_explicit_raw_daily_and_secret_not_in_provenance():
    def inspect(request):
        assert request.url.host == 'www.alphavantage.co'
        assert request.url.params['outputsize'] == 'compact'
        assert request.url.params['function'] == 'TIME_SERIES_DAILY'
    adapter = AlphaVantageAdapter('fixture-secret', clock=lambda: NOW, transport=mock_json({'Time Series (Daily)': {
        '2026-09-08': {'1. open': '100', '2. high': '102', '3. low': '99', '4. close': '101', '5. volume': '50'}}}, inspect=inspect))
    batch = await adapter.fetch('daily_bars', symbol='SPY')
    bars = bars_from_batch(batch, 'SPY', Timeframe.D1)
    assert bars[0].feed == Feed.DELAYED and bars[0].available_at == int(NOW.timestamp())
    assert 'fixture-secret' not in str(batch.provenance())
    assert batch.delay_seconds is None and not batch.historical_availability_verified


@pytest.mark.asyncio
async def test_missing_entitlement_and_rate_limit_never_fall_back():
    with pytest.raises(DataUnavailable, match='API key'):
        await FinnhubAdapter().fetch('quote', symbol='SPY')
    with pytest.raises(DataUnavailable, match='429'):
        await FinnhubAdapter('secret', transport=mock_json({'error': 'private'}, 429)).fetch('quote', symbol='SPY')
    with pytest.raises(DataUnavailable, match='paid'):
        await MassiveAdapter('secret').fetch('candles', symbol='SPY')
    with pytest.raises(DataUnavailable, match='not configured'):
        await DatabentoAdapter('secret').fetch('daily_bars', symbol='SPY')


@pytest.mark.asyncio
async def test_secret_echo_and_redirect_refused():
    with pytest.raises(DataUnavailable, match='credential material'):
        await FinnhubAdapter('sensitive-fixture', transport=mock_json({'error': 'sensitive-fixture'})).fetch('quote', symbol='SPY')
    with pytest.raises(DataUnavailable, match='302'):
        await FinnhubAdapter('secret', transport=mock_json({}, 302)).fetch('quote', symbol='SPY')


@pytest.mark.asyncio
async def test_fred_requests_historical_vintage_and_preserves_missing():
    def inspect(request):
        assert request.url.params['realtime_start'] == request.url.params['realtime_end'] == '2020-01-01'
    adapter = FredAdapter('secret', clock=lambda: NOW, transport=mock_json({'observations': [
        {'date': '2019-12-01', 'value': '.', 'realtime_start': '2020-01-01', 'realtime_end': '2020-01-01'}]}, inspect=inspect))
    batch = await adapter.fetch('observations', series_id='UNRATE', as_of='2020-01-01')
    assert batch.records[0]['value'] is None
    assert batch.records[0]['as_of'] == '2020-01-01'
    assert not batch.historical_availability_verified


@pytest.mark.asyncio
async def test_twelve_intraday_timezone_and_feed_are_explicit():
    def inspect(request):
        assert request.url.params['timezone'] == 'UTC'
        assert request.url.params['adjust'] == 'none'
    adapter = TwelveDataAdapter('secret', clock=lambda: NOW, transport=mock_json({'status': 'ok', 'values': [
        {'datetime': '2026-09-09 14:30:00', 'open': '100', 'high': '101', 'low': '99', 'close': '100', 'volume': '3'}]}, inspect=inspect))
    batch = await adapter.fetch('candles', symbol='SPY', timeframe=Timeframe.M5)
    assert batch.records[0]['time'] == int(datetime(2026, 9, 9, 14, 30, tzinfo=timezone.utc).timestamp())
    assert bars_from_batch(batch, 'SPY', Timeframe.M5)[0].feed == Feed.DELAYED


@pytest.mark.asyncio
async def test_sec_paths_cik_validation_and_identity():
    def inspect(request):
        assert request.url.path == '/submissions/CIK0000320193.json'
        assert request.headers['user-agent'] == 'Selery researcher@example.com'
    adapter = SecAdapter('Selery researcher@example.com', transport=mock_json({'cik': '320193'}, inspect=inspect))
    assert (await adapter.fetch('submissions', cik='320193')).records[0]['cik'] == '320193'
    with pytest.raises(DataUnavailable, match='invalid CIK'):
        await adapter.fetch('submissions', cik='../private')


@pytest.mark.asyncio
async def test_french_daily_factor_units_and_archive_parsing():
    output = io.BytesIO()
    with zipfile.ZipFile(output, 'w') as archive:
        archive.writestr('daily.csv', 'Notes\n,Mkt-RF,SMB,HML,RF\n20260908,0.5,-0.2,0.1,0.02\n')
    adapter = FrenchAdapter(clock=lambda: NOW, transport=httpx.MockTransport(lambda request: httpx.Response(200, content=output.getvalue())))
    batch = await adapter.fetch('daily_three_factors')
    assert batch.records[0]['market_minus_rf_percent'] == .5
    assert batch.records[0]['date'] == '2026-09-08'


def batch(feed=Feed.IEX, provider='fixture', close=101):
    return DataBatch(provider, 'candles', feed, NOW, [{'time': int((NOW - timedelta(hours=1)).timestamp()),
        'open': 100, 'high': 103, 'low': 99, 'close': close, 'volume': 10}], 'https://example.com/fixture', raw=b'{"fixture":true}')


def test_archive_hash_integrity_and_path_safety(tmp_path):
    archive = RawArchive(tmp_path)
    digest = archive.put(batch())
    assert digest == archive.put(batch())
    assert archive.get(digest)['provenance']['feed'] == 'iex'
    with pytest.raises(DataUnavailable, match='Invalid archive'):
        archive.get('../bad')
    (tmp_path / f'{digest}.json').write_text('{}')
    with pytest.raises(DataUnavailable, match='integrity'):
        archive.get(digest)


def test_ingestion_is_durable_idempotent_feed_separate_and_asof_safe(tmp_path):
    store, archive = Store(f'sqlite:///{tmp_path}/research.db'), RawArchive(tmp_path / 'raw')
    result = ingest_batch(store, archive, batch(), 'SPY', Timeframe.M5)
    assert result['inserted'] == 1
    assert ingest_batch(store, archive, batch(), 'SPY', Timeframe.M5)['unchanged'] == 1
    assert ingest_batch(store, archive, batch(Feed.SIP), 'SPY', Timeframe.M5)['inserted'] == 1
    kwargs = dict(symbol='SPY', timeframe=Timeframe.M5, feed=Feed.IEX, source='fixture:candles')
    assert replay_bars(store, as_of=NOW - timedelta(seconds=1), **kwargs) == []
    assert len(replay_bars(Store(f'sqlite:///{tmp_path}/research.db'), as_of=NOW, **kwargs)) == 1
    with pytest.raises(DataUnavailable, match='Source/version collision'):
        ingest_batch(store, archive, batch(provider='another'), 'SPY', Timeframe.M5)
    with pytest.raises(DataUnavailable, match='revision conflicts'):
        ingest_batch(store, archive, batch(close=102), 'SPY', Timeframe.M5)
    assert replay_bars(store, as_of=NOW, **kwargs)[0].close == 101


def test_catalog_is_configuration_only_and_no_paid_adapter_runs():
    catalog = provider_catalog()
    assert {item['provider'] for item in catalog} == {'finnhub', 'alpha_vantage', 'twelve_data', 'fred', 'sec', 'ken_french', 'yfinance', 'massive', 'databento', 'alpaca_historical_sip'}
    assert all(not item['automatic_fallback'] for item in catalog)
    assert not next(item for item in catalog if item['provider'] == 'massive')['configured']
