import { createSeleryChart } from "@selery/shared/src/chart";
import { ChartResponseSchema } from "@selery/shared";
let rendered: ReturnType<typeof createSeleryChart> | undefined;
const bridge = window as unknown as {
  ReactNativeWebView: { postMessage: (s: string) => void };
  renderSelery: (data: unknown) => void;
};
bridge.renderSelery = (data: unknown) => {
  try {
    const parsed = ChartResponseSchema.parse(data);
    rendered?.destroy();
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
