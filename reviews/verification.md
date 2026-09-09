# Verification evidence — September 9, 2026

These are local terminal results, not remote deployment or iPhone acceptance. The Python run includes installed optional scientific libraries. Statements without direct runtime exercise remain marked pending in the coverage matrix and wave reviews.

## Clean installation and dependency audit

Actual `npm ci` output:

```text
added 692 packages, and audited 698 packages in 10s
64 packages are looking for funding
found 0 vulnerabilities
```

The local npm policy emitted warnings about unapproved esbuild/fsevents install scripts; installed platform binaries nevertheless passed the subsequent web and native builds. The normal command completed successfully. `uv sync --frozen --group ml` installed the locked scientific group after explicitly constraining modern Numba. macOS LightGBM required OpenMP (`libomp`); one-thread Torch sequence execution is regression-tested.

## TypeScript and shared behavior

```text
Tasks: 2 successful, 2 total
Cached: 0 cached, 2 total
Time: 1.251s
Shared cache and reconnect tests passed
Bounded URI decoder behavior passed
```

The mobile type issue was caused by incompatible Zod generic composition, not insufficient heap allocation. Schema composition now stays in shared; resource parsers accept a structural parse method. Isolated mobile check measured roughly 380 MiB peak RSS.

## Python tests and statement coverage

```text
................................................. [ 29%]
........................................................................ [ 72%]
.............................................                            [100%]
=============================== warnings summary ===============================
.venv/lib/python3.12/site-packages/fastapi/testclient.py:1
  /Users/krishmalik/Documents/code/stocktradingapp/.venv/lib/python3.12/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

.venv/lib/python3.12/site-packages/starlette/testclient.py:53
  /Users/krishmalik/Documents/code/stocktradingapp/.venv/lib/python3.12/site-packages/starlette/testclient.py:53: DeprecationWarning: The anyio.abc.BlockingPortal alias is deprecated, use anyio.from_thread.BlockingPortal instead.
    _PortalFactoryType = Callable[[], AbstractContextManager[anyio.abc.BlockingPortal]]

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
================================ tests coverage ================================
______________ coverage: platform darwin, python 3.12.14-final-0 _______________

Name                                                       Stmts   Miss  Cover
------------------------------------------------------------------------------
apps/api/selery_api/__init__.py                                0      0   100%
apps/api/selery_api/adapters.py                              332    103    69%
apps/api/selery_api/assistant.py                              63     18    71%
apps/api/selery_api/auth.py                                   48      0   100%
apps/api/selery_api/config.py                                 31      7    77%
apps/api/selery_api/domain.py                                151     20    87%
apps/api/selery_api/ingestion.py                              87      8    91%
apps/api/selery_api/live_stream.py                            41     41     0%
apps/api/selery_api/main.py                                  329    145    56%
apps/api/selery_api/ml.py                                    427    108    75%
apps/api/selery_api/model_registry.py                        120     25    79%
apps/api/selery_api/news_pipeline.py                         175     17    90%
apps/api/selery_api/notifications.py                         215     41    81%
apps/api/selery_api/outcomes.py                               48      1    98%
apps/api/selery_api/providers.py                              94     42    55%
apps/api/selery_api/research.py                              148      4    97%
apps/api/selery_api/research_stats.py                         81     10    88%
apps/api/selery_api/storage.py                                66      0   100%
apps/api/selery_api/worker.py                                 37     37     0%
packages/shared/python/selery_shared/__init__.py               0      0   100%
packages/shared/python/selery_shared/costs.py                102      3    97%
packages/shared/python/selery_shared/indicators.py            90     12    87%
packages/shared/python/selery_shared/models.py               239      1    99%
packages/shared/python/selery_shared/structure.py             23      0   100%
packages/strategies/python/selery_strategies/__init__.py       0      0   100%
packages/strategies/python/selery_strategies/advanced.py     197     61    69%
packages/strategies/python/selery_strategies/alpha.py        252      3    99%
packages/strategies/python/selery_strategies/baseline.py      18      0   100%
packages/strategies/python/selery_strategies/library.py      158      6    96%
------------------------------------------------------------------------------
TOTAL                                                       3572    713    80%
Coverage JSON written to file docs/coverage.json
166 passed, 2 warnings, 23 subtests passed in 16.98s
```

## Web production build

```text
> selery@0.1.0 build
> npm run build --workspace @selery/web


> @selery/web@0.1.0 build
> next build

   ▲ Next.js 15.5.25

   Creating an optimized production build ...
 ✓ Compiled successfully in 518ms
   Linting and checking validity of types ...
   Collecting page data ...
   Generating static pages (0/4) ...
   Generating static pages (1/4) 
   Generating static pages (2/4) 
   Generating static pages (3/4) 
 ✓ Generating static pages (4/4)
   Finalizing page optimization ...
   Collecting build traces ...

Route (app)                                 Size  First Load JS
┌ ○ /                                    86.9 kB         189 kB
├ ○ /_not-found                            992 B         104 kB
└ ƒ /api/v1/[...path]                      119 B         103 kB
+ First Load JS shared by all             103 kB
  ├ chunks/18-2c82660ce7c4918d.js        46.4 kB
  ├ chunks/87c73c54-24122e7b92478d00.js  54.2 kB
  └ other shared chunks (total)          1.89 kB


○  (Static)   prerendered as static content
ƒ  (Dynamic)  server-rendered on demand
```

## Native iOS/Android export

```text
> @selery/mobile@0.1.0 export
> npm run chart:bundle && expo export --platform ios --platform android


> @selery/mobile@0.1.0 chart:bundle
> node scripts/bundle-chart.mjs

Bundled local chart (247949 bytes)
Expo Autolinking module resolution enabled
Starting Metro Bundler

iOS Bundled 3164ms apps/mobile/node_modules/expo-router/entry.js (1215 modules)
Android Bundled 5274ms apps/mobile/node_modules/expo-router/entry.js (1352 modules)

› Assets (36):
../../node_modules/@expo-google-fonts/inter/400Regular/Inter_400Regular.ttf (342KB)
../../node_modules/@expo-google-fonts/jetbrains-mono/400Regular/JetBrainsMono_400Regular.ttf (115KB)
../../node_modules/@expo-google-fonts/material-symbols/400Regular/MaterialSymbols_400Regular.ttf (965KB)
node_modules/expo-router/assets/arrow_down.png (9.5KB)
node_modules/expo-router/assets/arrow_right.xml (307B)
node_modules/expo-router/assets/checkmark.xml (312B)
node_modules/expo-router/assets/error.png (469B)
node_modules/expo-router/assets/file.png (138B)
node_modules/expo-router/assets/forward.png (188B)
node_modules/expo-router/assets/pkg.png (364B)
node_modules/expo-router/assets/react-navigation/elements/back-icon-mask.png (653B)
node_modules/expo-router/assets/react-navigation/elements/back-icon.png (8 variations | 359B)
node_modules/expo-router/assets/react-navigation/elements/clear-icon.png (4 variations | 425B)
node_modules/expo-router/assets/react-navigation/elements/close-icon.png (4 variations | 235B)
node_modules/expo-router/assets/react-navigation/elements/search-icon.png (7 variations | 592B)
node_modules/expo-router/assets/sitemap.png (465B)
node_modules/expo-router/assets/unmatched.png (4.8KB)

› ios bundles (1):
_expo/static/js/ios/entry-0b21e68294f7f88cc90d8a5d9e613f54.hbc (3.2MB)

› android bundles (1):
_expo/static/js/android/entry-b3137d7b67de5d312215fa841f15f8e4.hbc (3.5MB)

› Files (1):
metadata.json (3.6KB)

Exported: dist
```

## Production browser checks

```text
Running 3 tests using 1 worker

(node:38130) Warning: The 'NO_COLOR' env is ignored due to the 'FORCE_COLOR' env being set.
(Use `node --trace-warnings ...` to show where the warning was created)
  ✓  1 tests/browser/workspace.spec.ts:5:5 › watchlist chart and feed limitations render without browser errors (1.8s)
  ✓  2 tests/browser/workspace.spec.ts:13:5 › keyboard command palette changes view (348ms)
  ✓  3 tests/browser/workspace.spec.ts:20:5 › informational sizing uses backend limits (358ms)

  3 passed (2.9s)
```

## Shared chart behavior and desktop timing

```text
{
  "status": "passed",
  "replayBars": 50,
  "replaySignals": [
    "known"
  ],
  "replayPoints": 50,
  "sourceBars": 2000,
  "reused": true,
  "panePreserved": true,
  "before": {
    "from": 1780006000,
    "to": 1780024000
  },
  "after": {
    "from": 1780006000,
    "to": 1780024000
  },
  "rebuilt": true,
  "toggledRange": {
    "from": 1780006000,
    "to": 1780024000
  },
  "p95Ms": 1.9000000357627869,
  "identityStable": true
}
```

## Authored/generated/history security scan

```text
PASS: 194 authored files and 172 build artifacts scanned; no prohibited endpoints in authored source/history or credential values in source/artifacts/history; .env absent from Git history.
```

## npm audit summary

```json
{
  "info": 0,
  "low": 0,
  "moderate": 0,
  "high": 0,
  "critical": 0,
  "total": 0
}
```

## Scope and remaining evidence

- Provider probes are in [alpaca-verification.json](../docs/alpaca-verification.json) and [live-smoke.json](../docs/live-smoke.json). No account query was made.
- [Resource profile](../docs/runtime-profile.json) is an in-process fixture measurement. The separate chart timing above measures synchronous desktop chart update calls, not touch-to-paint on an iPhone.
- A consistent SQLite snapshot was created in a temporary location using the backup script and passed integrity checking. No PostgreSQL restore rehearsal was performed.
- Core Python statement coverage is 80%; the live upstream module and Arq worker have zero fixture coverage, and some optional/error paths remain untested. No TypeScript coverage percentage is claimed.
- Docker/Timescale/Redis stack execution, hosted CI, Vercel/Railway deployment, signed native installation, TestFlight and real-device/push behavior remain pending.
- The six wave reviews mark full acceptance FAIL where original scope remains incomplete. Passing these tests does not erase missing features.
