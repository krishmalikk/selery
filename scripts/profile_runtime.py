"""Read-only fixture benchmark, not an estimate of cloud billing or phone response."""
import json
import platform
import resource
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for folder in ('apps/api', 'packages/shared/python', 'packages/strategies/python'):
    sys.path.insert(0, str(ROOT / folder))
from fastapi.testclient import TestClient
from selery_api.config import Config
from selery_api.main import create_app

config = Config('https://paper-api.alpaca.markets', '', '', 'fixture-benchmark-password',
                'fixture-benchmark-session-secret-long', 'fixtures', 'sqlite:///:memory:', (), 0)
results = {}
with TestClient(create_app(config)) as client:
    client.post('/api/v1/auth/login', json={'password': config.password}).raise_for_status()
    for name, method, url, body in [
        ('watchlist', 'GET', '/api/v1/watchlist', None),
        ('chart_1000', 'GET', '/api/v1/chart/SPY?timeframe=5m', None),
        ('daily_research', 'POST', '/api/v1/research', {'symbol': 'SPY', 'timeframe': '1D'}),
    ]:
        samples = []
        for _ in range(10):
            started = time.perf_counter()
            response = client.request(method, url, json=body)
            response.raise_for_status()
            samples.append((time.perf_counter() - started) * 1000)
        results[name] = {'median_ms': round(statistics.median(samples), 2),
                         'max_ms': round(max(samples), 2), 'runs': len(samples)}
peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
payload = {'recorded_at': datetime.now(timezone.utc).isoformat(), 'python': platform.python_version(),
           'platform': platform.platform(), 'peak_rss_mib': round(peak / (1024**2 if sys.platform == 'darwin' else 1024), 2),
           'measurements': results,
           'limits': 'In-process fixtures, one client, SQLite memory; excludes persistent database, Redis, network, mobile, training and cloud overhead. Not a hosting price estimate.'}
print(json.dumps(payload, indent=2))
(ROOT / 'docs/runtime-profile.json').write_text(json.dumps(payload, indent=2) + '\n')
