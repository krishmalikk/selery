import { createSeleryChart, prepareChartData } from "@selery/shared/src/chart";
import { ChartResponseSchema } from "@selery/shared";
let rendered: ReturnType<typeof createSeleryChart> | undefined;
const bridge = window as unknown as {
  ReactNativeWebView: { postMessage: (s: string) => void };
  renderSelery: (data: unknown) => void;
};
bridge.renderSelery = (data: unknown) => {
  try {
    const parsed = prepareChartData(ChartResponseSchema.parse(data));
    if (rendered) {
      rendered.update(parsed);
      return;
    }
    rendered = createSeleryChart(
      document.getElementById("chart")!,
      parsed,
      (signal) =>
        bridge.ReactNativeWebView.postMessage(
          JSON.stringify({ type: "signal", id: signal.id }),
        ),
    );
  } catch {
    bridge.ReactNativeWebView.postMessage(
      JSON.stringify({
        type: "error",
        message: "Chart data could not be rendered",
      }),
    );
  }
};
bridge.ReactNativeWebView.postMessage(JSON.stringify({ type: "ready" }));
