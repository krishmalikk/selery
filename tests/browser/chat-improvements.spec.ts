import { expect, test, type Page } from "@playwright/test";
import type { Signal } from "../../packages/shared/src/contracts";

const timestamp = "2026-09-09T15:00:00Z";
async function fixture(page: Page, withSignal = false) {
  const signal: Signal = { id: "dated-signal-1", symbol: "SPY", strategy: "ema_crossover", strategy_version: "1", timeframe: "5m", time: 1788966000, available_at: 1788966300, direction: "bullish", reference_price: 101, stop: 99, target: 104, horizon_bars: 20, confidence: null, confidence_reason: "No calibrated model", feed: "iex", features: {}, explanation: "Synthetic finalized-bar crossover." };
  const creations: Record<string, unknown>[] = [];
  const conversation = { id: "improvement-thread", symbol: "SPY", title: "SPY research", created_at: timestamp, updated_at: timestamp, signal: null as Signal | null, chart_start: null as number | null, chart_end: null as number | null, summary: null as string | null, summary_at: null as string | null };
  const citations = [{ label: "Dated fixture bars", timestamp, data_id: "bars-1", url: "https://example.com/source", provider: "Fixture provider", feed: "iex", available_at: timestamp, observation: "SPY closed at 101 in this synthetic bar." }];
  const detail = { conversation, messages: [] as Record<string, unknown>[] };
  let release: (() => void) | undefined;
  let requests = 0;
  const searches: string[] = [];
  await page.route("**/api/v1/**", async (route) => {
    const request = route.request(), url = new URL(request.url()), path = url.pathname.replace("/api/v1", "");
    const json = (body: unknown, status = 200) => route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });
    if (path === "/settings") return json({ data_mode: "fixtures", feed: "iex", llm_monthly_cap_usd: 5, llm_spent_usd: 0, llm_enabled: true, disclaimer: "Selery is research software that displays analysis. It does not execute, recommend, or place trades." });
    if (path === "/watchlist") return json({ quotes: [], data_mode: "fixtures" });
    if (path === "/news") return json({ items: [], retrieved_at: timestamp, stale: false });
    if (path.startsWith("/chart/") || path.endsWith("/chart")) return json({ symbol: "SPY", timeframe: url.searchParams.get("timeframe") || "5m", bars: [{ symbol: "SPY", time: 1788966000, available_at: 1788966300, open: 100, high: 102, low: 99, close: 101, volume: 100, feed: "iex", finalized: true }], indicators: {}, signals: withSignal ? [signal] : [], capabilities: [], provenance: { provider: "Deterministic fixture", feed: "iex", observed_at: timestamp, available_at: timestamp, retrieved_at: timestamp, stale: true, synthetic: true, version: "1" } });
    if (path === "/conversations") {
      if (request.method() === "POST") {
        const body = request.postDataJSON(); creations.push(body);
        if (body.signal_id) { conversation.signal = signal; conversation.chart_start = body.chart_start; conversation.chart_end = body.chart_end; }
        return json(conversation);
      }
      const q = url.searchParams.get("q") || ""; searches.push(q);
      return json(conversation.title.toLowerCase().includes(q.toLowerCase()) || conversation.symbol.toLowerCase().includes(q.toLowerCase()) ? [conversation] : []);
    }
    if (path.endsWith("/rename")) { conversation.title = request.postDataJSON().title; return json(conversation); }
    if (path.endsWith("/summary")) { conversation.summary = "Conversation history: the user asked about dated SPY evidence."; conversation.summary_at = timestamp; return json(conversation); }
    if (path === `/conversations/${conversation.id}`) {
      if (request.method() === "PATCH") { conversation.title = request.postDataJSON().title; return json(conversation); }
      return json(detail);
    }
    if (path.endsWith("/messages")) {
      requests++;
      const body = request.postDataJSON(), id = `${conversation.id}:${body.request_id}`;
      const user = { id, conversation_id: conversation.id, role: "user", message: body.message, created_at: timestamp, status: "complete", error: null, citations: [], mode: null, cost_usd: 0, phase: null };
      detail.messages.push(user, { ...user, id: `${id}:answer`, role: "assistant", status: "pending", mode: "llm", phase: "generating", citations, message: "**Early evidence** [bars-1]" });
      await new Promise<void>((resolve) => { release = resolve; });
      detail.messages[1] = { ...detail.messages[1], status: "complete", phase: null, message: "**Final evidence**\n\n- Dated result [bars-1]\n- Unsupported claim [invented-id]\n\n<img src=x onerror=alert(1)> [unsafe](javascript:alert(1))" };
      return json(detail);
    }
    return json([]);
  });
  await page.goto("/?view=Assistant");
  await page.getByRole("button", { name: "Start conversation", exact: true }).click();
  return { detail, searches, creations, release: () => release?.(), requests: () => requests };
}

test("streams saved text while a request is pending and pauses display without resending", async ({ page }) => {
  const app = await fixture(page);
  await page.getByLabel("Message about SPY", { exact: true }).fill("Explain dated evidence");
  await page.getByRole("button", { name: "Send", exact: true }).click();
  await expect(page.locator(".research-answer strong").filter({ hasText: "Early evidence" })).toBeVisible();
  await expect(page.getByText("Generating response…", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Stop display", exact: true }).click();
  await expect(page.getByText("Display paused. The request continues and may still incur cost.")).toBeVisible();
  app.release();
  await expect(page.getByRole("button", { name: "Send", exact: true })).toBeDisabled();
  await expect(page.getByText("Final evidence", { exact: true })).toHaveCount(0);
  await page.getByRole("button", { name: "Resume display", exact: true }).click();
  await expect(page.locator(".research-answer strong").filter({ hasText: "Final evidence" })).toBeVisible();
  expect(app.requests()).toBe(1);
  await page.getByRole("button", { name: "Evidence bars-1", exact: true }).click();
  const card = page.getByRole("region", { name: "Evidence details", exact: true });
  await expect(card).toContainText("Fixture provider");
  await expect(card).toContainText("IEX only");
  await expect(card).toContainText("SPY closed at 101 in this synthetic bar.");
  await expect(page.getByText("[invented-id] (unknown source)", { exact: true })).toBeVisible();
  await expect(page.locator('.research-answer img, .research-answer script, .research-answer a[href^="javascript:"]')).toHaveCount(0);
  await expect(page.locator(".research-answer ul li")).toHaveCount(2);
});

test("renames and searches threads and creates an explicitly attributed history summary", async ({ page }) => {
  const app = await fixture(page);
  app.detail.messages.push({ id: "past", conversation_id: "improvement-thread", role: "user", message: "Earlier research question", created_at: timestamp, status: "complete", error: null, citations: [], mode: null, cost_usd: 0, phase: null });
  await page.getByRole("navigation", { name: "Saved conversations" }).getByRole("button", { name: /SPY/ }).click();
  await page.getByRole("button", { name: "Rename", exact: true }).click();
  await page.getByLabel("Conversation title", { exact: true }).fill("Opening range research");
  await page.getByRole("button", { name: "Save title", exact: true }).click();
  await expect(page.getByRole("navigation", { name: "Saved conversations" })).toContainText("Opening range research");
  await page.getByLabel("Search conversations", { exact: true }).fill("missing-symbol");
  await expect(page.getByRole("navigation", { name: "Saved conversations" }).getByRole("button")).toHaveCount(0);
  expect(app.searches).toContain("missing-symbol");
  await page.getByRole("button", { name: "Summarize history", exact: true }).click();
  await page.getByText("Conversation history summary", { exact: true }).click();
  await expect(page.getByText("Conversation history: the user asked about dated SPY evidence.", { exact: true })).toBeVisible();
  await expect(page.getByText(/Not current market evidence\./)).toBeVisible();
});


test("the selected signal creates a fixed dated chart conversation without a paid request", async ({ page }) => {
  const app = await fixture(page, true);
  await page.getByRole("navigation").first().getByRole("button", { name: "Overview", exact: true }).click();
  await page.getByRole("row").filter({ hasText: "ema crossover" }).click();
  await page.getByRole("button", { name: "Ask about this signal", exact: true }).click();
  await expect(page.getByText(/Signal dated-signal-1 ·/)).toBeVisible();
  await expect(page.getByText(/Dated signal chart:/)).toBeVisible();
  const chart = page.getByRole("region", { name: "SPY chart context", exact: true });
  await expect(chart.getByRole("button", { name: "1h", exact: true })).toBeDisabled();
  await expect(chart.locator("canvas").first()).toBeVisible();
  expect(app.creations.at(-1)).toMatchObject({ symbol: "SPY", signal_id: "dated-signal-1", timeframe: "5m", chart_start: 1788966000, chart_end: 1788966000 });
  expect(app.requests()).toBe(0);
});
