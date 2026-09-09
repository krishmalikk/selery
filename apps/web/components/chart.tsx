"use client";
import { useEffect, useRef } from "react";
import { type ChartResponse, type Signal } from "@selery/shared";
import {
  createSeleryChart,
  prepareChartData,
  defaultChartIndicators,
} from "@selery/shared/src/chart";
export default function ResearchChart({
  data,
  onSignal,
  replay,
  indicators = defaultChartIndicators,
}: {
  data: ChartResponse;
  onSignal: (s: Signal) => void;
  replay: number;
  indicators?: readonly string[];
}) {
  const container = useRef<HTMLDivElement>(null),
    renderer = useRef<ReturnType<typeof createSeleryChart> | null>(null);
  const callback = useRef(onSignal);
  callback.current = onSignal;
  useEffect(() => {
    if (!container.current) return;
    const visible = prepareChartData(data, replay, indicators);
    if (renderer.current) renderer.current.update(visible);
    else
      renderer.current = createSeleryChart(
        container.current,
        visible,
        (signal) => callback.current(signal),
      );
  }, [data, replay, indicators]);
  useEffect(
    () => () => {
      renderer.current?.destroy();
      renderer.current = null;
    },
    [],
  );
  return (
    <div
      className="chart-canvas"
      ref={container}
      aria-label={`${data.symbol} candlestick chart and selected backend indicators. Resize oscillator panes by dragging their separators. Signal details are also available below.`}
    />
  );
}
