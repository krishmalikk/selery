"""Durable ingestion and as-of replay for explicitly selected research datasets."""
from __future__ import annotations

import base64
import hashlib
import json
import math
import os
import re
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import and_, insert, select
from sqlalchemy.exc import IntegrityError

from selery_shared.models import Bar, Feed, Timeframe
from .adapters import DataBatch, DataUnavailable, bars_from_batch
from .storage import Store, bars_table

UTC = timezone.utc


class RawArchive:
    """Immutable local archive. Store on a persistent encrypted volume in deployment."""
    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)

    def put(self, batch: DataBatch) -> str:
        envelope = {'provenance': batch.provenance(), 'raw_base64': base64.b64encode(batch.raw).decode('ascii'),
                    'records': batch.records}
        encoded = json.dumps(envelope, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
        digest = hashlib.sha256(encoded).hexdigest()
        path = self.root / f'{digest}.json'
        try:
            descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError:
            if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
                raise DataUnavailable('Archive integrity failure')
            return digest
        with os.fdopen(descriptor, 'wb') as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        return digest

    def get(self, digest: str) -> dict:
        if not re.fullmatch(r'[a-f0-9]{64}', digest):
            raise DataUnavailable('Invalid archive reference')
        encoded = (self.root / f'{digest}.json').read_bytes()
        if hashlib.sha256(encoded).hexdigest() != digest:
            raise DataUnavailable('Archive integrity failure')
        envelope = json.loads(encoded)
        raw = base64.b64decode(envelope['raw_base64'], validate=True)
        if hashlib.sha256(raw).hexdigest() != envelope['provenance']['raw_sha256']:
            raise DataUnavailable('Raw payload integrity failure')
        return envelope


def ingest_batch(store: Store, archive: RawArchive, batch: DataBatch, symbol: str, timeframe: Timeframe):
    """Archive before normalization; preserve conflicting revisions without overwriting history."""
    reference = archive.put(batch)
    bars = bars_from_batch(batch, symbol, timeframe)
    inserted = unchanged = pending = 0
    source = f'{batch.provider}:{batch.dataset}'
    with store.engine.begin() as connection:
        for bar in bars:
            if not bar.finalized:
                pending += 1
                continue
            stamp = datetime.fromtimestamp(bar.time, UTC)
            key = and_(bars_table.c.symbol == symbol, bars_table.c.feed == str(batch.feed),
                       bars_table.c.timeframe == str(timeframe), bars_table.c.time == stamp)
            row = connection.execute(select(bars_table).where(key)).mappings().first()
            values = dict(symbol=symbol, feed=str(batch.feed), timeframe=str(timeframe), time=stamp,
                          available_at=datetime.fromtimestamp(bar.available_at, UTC), open=bar.open, high=bar.high,
                          low=bar.low, close=bar.close, volume=bar.volume, source=source, version=batch.version)
            if row is None:
                try:
                    with connection.begin_nested():
                        connection.execute(insert(bars_table).values(**values))
                    inserted += 1
                    continue
                except IntegrityError:
                    row = connection.execute(select(bars_table).where(key)).mappings().first()
            if row is None:
                raise DataUnavailable('Concurrent ingestion could not reconcile the stored bar')
            if row['source'] != source or row['version'] != batch.version:
                raise DataUnavailable('Source/version collision: select a separate dataset; no silent replacement')
            if any(not math.isclose(float(row[field]), values[field], rel_tol=0, abs_tol=1e-10)
                   for field in ('open', 'high', 'low', 'close', 'volume')):
                raise DataUnavailable(f'Source revision conflicts with immutable bars; raw archive {reference} preserves the response')
            unchanged += 1
    result = {'inserted': inserted, 'unchanged': unchanged, 'pending': pending, 'archive_id': reference,
              'provenance': batch.provenance(), 'symbol': symbol, 'timeframe': str(timeframe)}
    store.audit('data_ingestion', result)
    return result


def replay_bars(store: Store, *, symbol: str, timeframe: Timeframe, feed: Feed,
                as_of: datetime, source: str, limit: int = 2000) -> list[Bar]:
    if as_of.tzinfo is None or not 1 <= limit <= 10000:
        raise ValueError('Replay needs a timezone-aware as_of and a limit from 1 to 10000')
    query = select(bars_table).where(bars_table.c.symbol == symbol, bars_table.c.feed == str(feed),
             bars_table.c.timeframe == str(timeframe), bars_table.c.source == source,
             bars_table.c.available_at <= as_of).order_by(bars_table.c.time.desc()).limit(limit)
    with store.engine.connect() as connection:
        rows = list(connection.execute(query).mappings())
    def seconds(value):
        return int(value.replace(tzinfo=UTC).timestamp() if value.tzinfo is None else value.timestamp())
    return [Bar(symbol=symbol, feed=feed, time=seconds(row['time']), available_at=seconds(row['available_at']),
                open=row['open'], high=row['high'], low=row['low'], close=row['close'], volume=row['volume'], finalized=True)
            for row in reversed(rows)]
