import React, { useRef, useEffect, useState, useMemo } from "react";
import { View, Text } from "react-native";
import { WebView } from "react-native-webview";
import {
  ChartResponseSchema,
  type ChartResponse,
  type Signal,
} from "@selery/shared";
import { chartHtml } from "./chart-html";
import { styles } from "./ui";
export function NativeChart({
  data,
  onSignal,
  height = 420,
}: {
  data: ChartResponse;
  onSignal: (s: Signal) => void;
  height?: number;
}) {
  const ref = useRef<WebView>(null),
    [ready, setReady] = useState(false),
    [error, setError] = useState("");
  const source = useMemo(
    () => ({ html: chartHtml, baseUrl: "about:blank" }),
    [],
  );
  useEffect(() => {
    if (ready) {
      const safe = JSON.stringify(ChartResponseSchema.parse(data))
        .replace(/</g, "\\u003c")
        .replace(/\u2028/g, "\\u2028")
        .replace(/\u2029/g, "\\u2029");
      ref.current?.injectJavaScript(`window.renderSelery(${safe});true;`);
    }
  }, [data, ready]);
  return (
    <View style={{ height, borderRadius: 16, overflow: "hidden" }}>
      <WebView
        ref={ref}
        source={source}
        originWhitelist={["about:blank"]}
        javaScriptEnabled
        scrollEnabled={false}
        bounces={false}
        allowFileAccess={false}
        setSupportMultipleWindows={false}
        onShouldStartLoadWithRequest={(request) =>
          request.url === "about:blank"
        }
        onError={() => setError("Chart renderer unavailable")}
        onMessage={({ nativeEvent }) => {
          try {
            const event = JSON.parse(nativeEvent.data);
            if (event.type === "ready") setReady(true);
            if (event.type === "error") setError(event.message);
            if (event.type === "signal") {
              const signal = data.signals.find((s) => s.id === event.id);
              if (signal) onSignal(signal);
            }
          } catch {
            setError("Invalid chart message");
          }
        }}
      />
      {!!error && <Text style={styles.warning}>{error}</Text>}
    </View>
  );
}
