import assert from "node:assert/strict";
import { resolve } from "node:path";
import { build } from "esbuild";
import { chromium } from "playwright";

async function main() {
  const bundle = await build({
    entryPoints: [resolve("packages/shared/src/chart.ts")],
    bundle: true,
    write: false,
    format: "iife",
    globalName: "chartHelpers",
    platform: "browser",
  });
  const browser = await chromium.launch({ headless: true });
  try {
    const page = await browser.newPage({
      viewport: { width: 1200, height: 900 },
    });
    await page.route("**/*", (route) => route.abort());
    await page.setContent(
      '<div id="chart" style="width:1000px;height:600px"></div>',
    );
    await page.addScriptTag({
      content: "window.__name = (fn) => fn;" + bundle.outputFiles[0].text,
    });
    const proof = await page.evaluate(async () => {
      const helpers = (window as any).chartHelpers;
      const frame = () =>
        new Promise((resolve) =>
          requestAnimationFrame(() => requestAnimationFrame(resolve)),
        );
      const start = 1_780_000_000;
      const bars = Array.from({ length: 2000 }, (_, i) => ({
        symbol: "SPY",
        time: start + i * 300,
        available_at: start + (i + 1) * 300,
        open: 100,
        high: 102,
        low: 99,
        close: 101,
        volume: 100,
        feed: "synthetic",
        finalized: true,
      }));
      const base: any = {
        symbol: "SPY",
        timeframe: "5m",
        bars,
        indicators: {
          ema9: bars.map((bar) => ({ time: bar.time, value: 100 })),
          rsi14: bars.map((bar) => ({ time: bar.time, value: 50 })),
        },
        signals: [
          {
            id: "known",
            symbol: "SPY",
            strategy: "fixture",
            strategy_version: "1",
            timeframe: "5m",
            time: bars[49].time,
            available_at: bars[49].available_at,
            direction: "bullish",
            reference_price: 100,
            stop: 99,
            target: 102,
            horizon_bars: 5,
            confidence: null,
            confidence_reason: "Uncalibrated",
            feed: "synthetic",
            features: {},
            explanation: "Synthetic renderer test",
          },
          {
            id: "late",
            symbol: "SPY",
            strategy: "fixture",
            strategy_version: "1",
            timeframe: "5m",
            time: bars[49].time,
            available_at: bars[51].available_at,
            direction: "bearish",
            reference_price: 100,
            stop: 102,
            target: 99,
            horizon_bars: 5,
            confidence: null,
            confidence_reason: "Uncalibrated",
            feed: "synthetic",
            features: {},
            explanation: "Synthetic late availability test",
          },
        ],
        capabilities: [],
        provenance: {
          provider: "offline-test",
          feed: "synthetic",
          observed_at: "2026-06-01T00:00:00Z",
          available_at: "2026-06-01T00:00:00Z",
          retrieved_at: "2026-06-01T00:00:00Z",
          stale: true,
          synthetic: true,
          version: "1",
        },
      };
      const replay = helpers.prepareChartData(base, 50, ["ema9", "rsi14"]);
      const renderer = helpers.createSeleryChart(
        document.getElementById("chart"),
        base,
        () => {},
      );
      await frame();
      const firstChart = renderer.chart;
      renderer.chart
        .timeScale()
        .setVisibleRange({ from: bars[20].time, to: bars[80].time });
      await frame();
      const before = renderer.chart.timeScale().getVisibleRange();
      renderer.chart.panes()[1].setHeight(120);
      await frame();
      const paneBefore = renderer.chart.panes()[1].getHeight();
      renderer.update({
        ...base,
        bars: [
          ...bars,
          {
            ...bars.at(-1),
            time: bars.at(-1)!.time + 300,
            available_at: bars.at(-1)!.available_at + 300,
          },
        ],
      });
      await frame();
      const after = renderer.chart.timeScale().getVisibleRange();
      const reused = renderer.chart === firstChart;
      const panePreserved =
        renderer.chart.panes()[1].getHeight() === paneBefore;
      const durations = [];
      for (let i = 0; i < 30; i++) {
        const t = performance.now();
        renderer.update(base);
        durations.push(performance.now() - t);
        await frame();
      }
      durations.sort((a, b) => a - b);
      renderer.update({ ...base, indicators: { ema9: base.indicators.ema9 } });
      const rebuilt = renderer.chart !== firstChart;
      await frame();
      const toggledRange = renderer.chart.timeScale().getVisibleRange();
      renderer.destroy();
      renderer.destroy();
      return {
        replayBars: replay.bars.length,
        replaySignals: replay.signals.map((signal: any) => signal.id),
        replayPoints: replay.indicators.ema9.length,
        sourceBars: base.bars.length,
        reused,
        panePreserved,
        before,
        after,
        rebuilt,
        toggledRange,
        p95Ms: durations[28],
        identityStable:
          helpers.chartIdentity(base) ===
          helpers.chartIdentity({
            ...base,
            indicators: {
              rsi14: base.indicators.rsi14,
              ema9: base.indicators.ema9,
            },
          }),
      };
    });
    assert.equal(proof.replayBars, 50);
    assert.equal(proof.replayPoints, 50);
    assert.deepEqual(proof.replaySignals, ["known"]);
    assert.equal(proof.sourceBars, 2000);
    assert.equal(proof.reused, true);
    assert.equal(proof.panePreserved, true);
    assert.deepEqual(proof.before, proof.after);
    assert.equal(proof.rebuilt, true);
    assert.deepEqual(proof.before, proof.toggledRange);
    assert.equal(proof.identityStable, true);
    console.log(JSON.stringify({ status: "passed", ...proof }, null, 2));
  } finally {
    await browser.close();
  }
}
main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
