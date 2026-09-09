import {
  createChart,
  CandlestickSeries,
  LineSeries,
  createSeriesMarkers,
  ColorType,
  CrosshairMode,
  type UTCTimestamp,
  type Time,
  type ISeriesApi,
  type IChartApi,
  type ISeriesMarkersPluginApi,
} from "lightweight-charts";
import type { ChartResponse, Signal } from "./contracts";
import { tokens } from "./tokens";

export const chartIndicatorGroups = [
  { id: "ema", label: "EMA 9 / 21", keys: ["ema9", "ema21"] },
  { id: "rsi", label: "RSI 14", keys: ["rsi14"] },
  { id: "sma", label: "SMA 50", keys: ["sma50"] },
  { id: "bb", label: "Bollinger bands", keys: ["bb_upper", "bb_lower"] },
  { id: "macd", label: "MACD", keys: ["macd"] },
  { id: "atr", label: "ATR 14", keys: ["atr14"] },
  { id: "vwap", label: "VWAP", keys: ["vwap"] },
] as const;
export const defaultChartIndicators = ["ema9", "ema21", "rsi14"];
const knownKeys = new Set<string>(
  chartIndicatorGroups.flatMap((group) => [...group.keys]),
);

/** Presentation filtering only: indicator values and signal decisions come from Python. */
export function prepareChartData(
  data: ChartResponse,
  replayCount = 0,
  indicators: readonly string[] = defaultChartIndicators,
): ChartResponse {
  const count =
    replayCount > 0
      ? Math.max(1, Math.min(data.bars.length, Math.floor(replayCount)))
      : data.bars.length;
  const bars = data.bars.slice(0, count),
    last = bars.at(-1);
  return {
    ...data,
    bars,
    indicators: Object.fromEntries(
      Object.entries(data.indicators)
        .filter(([key]) => indicators.includes(key) && knownKeys.has(key))
        .map(([key, points]) => [
          key,
          points.filter((point) => last && point.time <= last.time),
        ]),
    ),
    signals: data.signals.filter(
      (signal) =>
        last &&
        signal.time <= last.time &&
        signal.available_at <= last.available_at,
    ),
  };
}
export function chartIdentity(data: ChartResponse): string {
  return JSON.stringify([
    data.symbol,
    data.timeframe,
    data.provenance.feed,
    Object.keys(data.indicators)
      .filter((key) => knownKeys.has(key))
      .sort(),
  ]);
}

/** Shared DOM renderer. Refresh updates preserve time range; pane structure changes rebuild once. */
export function createSeleryChart(
  container: HTMLElement,
  initial: ChartResponse,
  onSignal: (signal: Signal) => void,
) {
  const c = tokens.color;
  let data = initial,
    identity = chartIdentity(initial),
    chart: IChartApi,
    candles: ISeriesApi<"Candlestick">,
    markers: ISeriesMarkersPluginApi<Time>,
    lines = new Map<string, ISeriesApi<"Line">>(),
    destroyed = false;
  const find = (time: unknown) =>
    data.signals.find((signal) => signal.time === time);
  const initialize = () => {
    chart = createChart(container, {
      autoSize: true,
      layout: {
        background: { type: ColorType.Solid, color: c.background },
        textColor: c.muted,
        fontFamily: "Inter, sans-serif",
        attributionLogo: true,
        panes: {
          enableResize: true,
          separatorColor: c.border,
          separatorHoverColor: c.accent,
        },
      },
      grid: {
        vertLines: { color: "#18231d" },
        horzLines: { color: "#18231d" },
      },
      crosshair: { mode: CrosshairMode.Normal },
      rightPriceScale: { borderColor: c.border },
      timeScale: {
        borderColor: c.border,
        timeVisible: data.timeframe !== "1D" && data.timeframe !== "1W",
      },
      handleScale: {
        pinch: true,
        mouseWheel: true,
        axisPressedMouseMove: true,
      },
      handleScroll: {
        horzTouchDrag: true,
        vertTouchDrag: false,
        mouseWheel: true,
        pressedMouseMove: true,
      },
    });
    candles = chart.addSeries(CandlestickSeries, {
      upColor: c.accent,
      downColor: c.negative,
      borderVisible: false,
      wickUpColor: c.accent,
      wickDownColor: c.negative,
    });
    lines = new Map();
    const colors: Record<string, string> = {
      ema9: c.accent,
      ema21: c.warning,
      sma50: "#89b9c7",
      vwap: "#96b6d2",
      bb_upper: "#627e94",
      bb_lower: "#627e94",
      rsi14: "#b4a4d0",
      macd: "#9ebbc0",
      atr14: "#c6aa89",
    };
    let pane = 0;
    for (const key of Object.keys(data.indicators)
      .filter((key) => knownKeys.has(key))
      .sort()) {
      const oscillator = ["rsi14", "macd", "atr14"].includes(key);
      const line = chart.addSeries(
        LineSeries,
        {
          color: colors[key],
          lineWidth: 1,
          priceLineVisible: false,
          lastValueVisible: oscillator,
          title: key.toUpperCase(),
        },
        oscillator ? ++pane : 0,
      );
      lines.set(key, line);
      if (key === "rsi14")
        for (const price of [30, 70])
          line.createPriceLine({
            price,
            color: "#574d3d",
            lineWidth: 1,
            lineStyle: 2,
            axisLabelVisible: false,
          });
      if (oscillator) chart.panes()[pane]?.setHeight(100);
    }
    markers = createSeriesMarkers(candles, []);
    chart.subscribeClick((event) => {
      const signal = find(event.time);
      if (signal) onSignal(signal);
    });
    // Opening a native sheet on hover interrupts crosshair exploration; selection is click/hold only.
  };
  const setData = () => {
    candles.setData(
      data.bars.map((bar) => ({
        time: bar.time as UTCTimestamp,
        open: bar.open,
        high: bar.high,
        low: bar.low,
        close: bar.close,
      })),
    );
    for (const [key, line] of lines)
      line.setData(
        data.indicators[key]
          .filter((point) => point.value !== null)
          .map((point) => ({
            time: point.time as UTCTimestamp,
            value: point.value!,
          })),
      );
    markers.setMarkers(
      data.signals.map((signal) => ({
        id: signal.id,
        time: signal.time as UTCTimestamp,
        position: signal.direction === "bullish" ? "belowBar" : "aboveBar",
        shape: signal.direction === "bullish" ? "arrowUp" : "arrowDown",
        color: signal.direction === "bullish" ? c.accent : c.negative,
        text: "",
      })),
    );
  };
  initialize();
  setData();
  chart!.timeScale().fitContent();
  let timer: ReturnType<typeof setTimeout> | undefined;
  const cancel = () => {
    if (timer) clearTimeout(timer);
    timer = undefined;
  };
  const touch = (event: TouchEvent) => {
    cancel();
    if (event.touches.length !== 1) return;
    const x = event.touches[0].clientX - container.getBoundingClientRect().left;
    timer = setTimeout(() => {
      const signal = find(chart.timeScale().coordinateToTime(x));
      if (signal) onSignal(signal);
    }, 450);
  };
  container.addEventListener("touchstart", touch, { passive: true });
  container.addEventListener("touchend", cancel);
  container.addEventListener("touchmove", cancel);
  container.addEventListener("touchcancel", cancel);
  return {
    get chart() {
      return chart;
    },
    update(next: ChartResponse) {
      if (destroyed) return;
      const sameInstrument =
        data.symbol === next.symbol &&
        data.timeframe === next.timeframe &&
        data.provenance.feed === next.provenance.feed;
      const range = sameInstrument ? chart.timeScale().getVisibleRange() : null;
      const logical = sameInstrument
        ? chart.timeScale().getVisibleLogicalRange()
        : null;
      const oldFirst = data.bars[0]?.time,
        newFirst = next.bars[0]?.time;
      const oldFirstInNext = next.bars.findIndex(
        (bar) => bar.time === oldFirst,
      );
      const newFirstInOld = data.bars.findIndex((bar) => bar.time === newFirst);
      const offset =
        oldFirstInNext >= 0
          ? oldFirstInNext
          : newFirstInOld >= 0
            ? -newFirstInOld
            : null;
      const nextIdentity = chartIdentity(next);
      data = next;
      if (nextIdentity !== identity) {
        cancel();
        chart.remove();
        identity = nextIdentity;
        initialize();
      }
      setData();
      if (logical && offset !== null && data.bars.length)
        chart
          .timeScale()
          .setVisibleLogicalRange({
            from: logical.from + offset,
            to: logical.to + offset,
          });
      else if (range && data.bars.length)
        chart.timeScale().setVisibleRange(range);
      else chart.timeScale().fitContent();
    },
    destroy() {
      if (destroyed) return;
      destroyed = true;
      cancel();
      container.removeEventListener("touchstart", touch);
      container.removeEventListener("touchend", cancel);
      container.removeEventListener("touchmove", cancel);
      container.removeEventListener("touchcancel", cancel);
      chart.remove();
    },
  };
}
