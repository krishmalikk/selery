import { expect, test, type Page } from "@playwright/test";
import type { Conversation, ConversationDetail, ConversationMessage } from "../../packages/shared/src/contracts";

const timestamp = "2026-09-09T15:00:00Z";
async function fixtureApp(page: Page) {
  const records = new Map<string, ConversationDetail>();
  const turns: { symbol: string; message: string; timeframe: string }[] = [];
  let failNext = false;
  let failChart = false;
  let held: Promise<void> | null = null;
  let release: (() => void) | null = null;
  await page.route("**/api/v1/**", async (route) => {
    const request = route.request(), url = new URL(request.url()), path = url.pathname.replace("/api/v1", "");
    const json = (data: unknown, status = 200) => route.fulfill({ status, contentType: "application/json", body: JSON.stringify(data) });
    if (path === "/settings") return json({ data_mode: "fixtures", feed: "iex", llm_monthly_cap_usd: 5, llm_spent_usd: 0, llm_enabled: true, disclaimer: "Selery is research software that displays analysis. It does not execute, recommend, or place trades." });
    if (path === "/watchlist") return json({ quotes: [], data_mode: "fixtures" });
    if (path === "/news") return json({ items: [], retrieved_at: timestamp, stale: false });
    if (path.startsWith("/chart/")) {
      if (failChart) return json({ detail: "Market data temporarily unavailable" }, 503);
      const symbol = path.split("/").pop();
      return json({ symbol, timeframe: url.searchParams.get("timeframe"), bars: [{ symbol, time: 1788966000, available_at: 1788966300, open: 100, high: 102, low: 99, close: 101, volume: 100, feed: "iex", finalized: true }], indicators: {}, signals: [], capabilities: [], provenance: { provider: "Deterministic browser fixture", feed: "iex", observed_at: timestamp, available_at: timestamp, retrieved_at: timestamp, stale: true, synthetic: true, version: "1" } });
    }
    if (path === "/conversations" && request.method() === "GET") return json([...records.values()].map((record) => record.conversation));
    if (path === "/conversations" && request.method() === "POST") {
      const { symbol } = request.postDataJSON();
      const conversation: Conversation = { id: `thread-${records.size + 1}`, symbol, title: `${symbol} research`, created_at: timestamp, updated_at: timestamp, signal: null, chart_start: null, chart_end: null, summary: null, summary_at: null };
      records.set(conversation.id, { conversation, messages: [] }); return json(conversation);
    }
    const match = path.match(/^\/conversations\/([^/]+)(\/messages)?$/);
    if (match) {
      const record = records.get(match[1]);
      if (!record) return json({ detail: "Conversation unavailable" }, 404);
      if (!match[2]) return json(record);
      const body = request.postDataJSON();
      turns.push({ symbol: record.conversation.symbol, message: body.message, timeframe: body.timeframe });
      const user: ConversationMessage = { id: `${record.conversation.id}:${body.request_id}`, conversation_id: record.conversation.id, role: "user", message: body.message, created_at: timestamp, status: failNext ? "failed" : "complete", error: failNext ? "Provider credits exhausted" : null, citations: [], mode: null, cost_usd: 0, phase: null };
      record.messages.push(user);
      if (failNext) { failNext = false; return json({ detail: "Provider credits exhausted" }, 503); }
      record.messages.push({ ...user, id: `${user.id}:answer`, role: "assistant", message: `Answer ${turns.length} about ${record.conversation.symbol}; ${record.messages.filter((message) => message.role === "user").length} questions in this conversation.`, mode: "llm", citations: [{ label: `${record.conversation.symbol} dated chart evidence`, timestamp, url: null, data_id: "fixture-bars", provider: "Fixture", feed: "iex", available_at: timestamp, observation: "Dated synthetic bars" }] });
      if (held) await held;
      return json(record);
    }
    return json([]);
  });
  await page.goto("/?view=Assistant");
  await expect(page.getByRole("heading", { name: "A conversation, centered on a stock." })).toBeVisible();
  return { turns, records, fail: () => { failNext = true; }, failChart: () => { failChart = true; }, hold: () => { held = new Promise<void>((resolve) => { release = resolve; }); }, release: () => { release?.(); held = null; } };
}

test("requires an explicit stock, supports follow-ups and reopens saved conversations", async ({ page }) => {
  const fixture = await fixtureApp(page);
  await expect(page.getByLabel("Message about SPY", { exact: true })).toHaveCount(0);
  expect(fixture.turns).toHaveLength(0);
  await page.getByLabel("Stock symbol", { exact: true }).fill("AAPL");
  await page.getByRole("button", { name: "Start conversation" }).click();
  const chart = page.getByRole("region", { name: "AAPL chart context", exact: true });
  await expect(chart.locator("canvas").first()).toBeVisible();
  expect(fixture.turns).toHaveLength(0);
  await chart.getByRole("button", { name: "1h", exact: true }).click();
  await page.getByLabel("Message about AAPL", { exact: true }).fill("What changed?");
  await page.getByRole("button", { name: "Send", exact: true }).click();
  await expect(page.getByText("Answer 1 about AAPL; 1 questions in this conversation.")).toBeVisible();
  await page.getByLabel("Message about AAPL", { exact: true }).fill("Explain that further.");
  await page.getByLabel("Message about AAPL", { exact: true }).press("Enter");
  await expect(page.getByText("Answer 2 about AAPL; 2 questions in this conversation.")).toBeVisible();
  expect(fixture.turns.map((turn) => turn.timeframe)).toEqual(["1h", "1h"]);
  await page.getByRole("button", { name: "New conversation", exact: true }).click();
  await page.getByLabel("Stock symbol", { exact: true }).fill("QQQ");
  await page.getByRole("button", { name: "Start conversation" }).click();
  await expect(page.getByRole("region", { name: "QQQ chart context", exact: true }).locator("canvas").first()).toBeVisible();
  await expect(page.getByRole("region", { name: "AAPL chart context", exact: true })).toHaveCount(0);
  await page.getByRole("navigation", { name: "Saved conversations" }).getByRole("button", { name: /AAPL/ }).click();
  await expect(page.getByText("Answer 2 about AAPL; 2 questions in this conversation.")).toBeVisible();
  await expect(page.getByRole("region", { name: "AAPL chart context", exact: true }).locator("canvas").first()).toBeVisible();
  await page.reload();
  await page.getByRole("navigation", { name: "Saved conversations" }).getByRole("button", { name: /AAPL/ }).click();
  await expect(page.getByText("Answer 1 about AAPL; 1 questions in this conversation.")).toBeVisible();
});

test("failed requests preserve the draft without fabricating an assistant answer", async ({ page }) => {
  const fixture = await fixtureApp(page);
  await page.getByRole("button", { name: "Start conversation" }).click();
  fixture.fail();
  await page.getByLabel("Message about SPY", { exact: true }).fill("Explain the current chart.");
  await page.getByRole("button", { name: "Send", exact: true }).click();
  await expect(page.getByRole("alert").filter({ hasText: "Provider credits exhausted" })).toBeVisible();
  await expect(page.getByLabel("Message about SPY", { exact: true })).toHaveValue("Explain the current chart.");
  await expect(page.locator(".conversation-message.assistant")).toHaveCount(0);
  await expect(page.getByText("Response failed: Provider credits exhausted", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Send", exact: true }).click();
  await expect(page.locator(".conversation-message.assistant")).toHaveCount(1);
  await expect(page.getByLabel("Message about SPY", { exact: true })).toHaveValue("");
});

test("late answers stay with their stock and chart failures keep dated context", async ({ page }) => {
  const fixture = await fixtureApp(page);
  await page.getByRole("button", { name: "Start conversation" }).click();
  fixture.hold();
  await page.getByLabel("Message about SPY", { exact: true }).fill("Explain SPY.");
  await page.getByRole("button", { name: "Send", exact: true }).click();
  await expect(page.getByRole("status").filter({ hasText: "Reading SPY evidence" })).toBeVisible();
  await page.getByRole("button", { name: "New conversation", exact: true }).click();
  await page.getByLabel("Stock symbol", { exact: true }).fill("QQQ");
  await page.getByRole("button", { name: "Start conversation" }).click();
  const chart = page.getByRole("region", { name: "QQQ chart context", exact: true });
  await expect(chart.locator("canvas").first()).toBeVisible();
  fixture.release();
  await expect(page.getByRole("heading", { name: "QQQ conversation", exact: true })).toBeVisible();
  await expect(page.getByText("Answer 1 about SPY; 1 questions in this conversation.")).toHaveCount(0);
  fixture.failChart();
  await page.getByRole("button", { name: "Refresh conversation chart", exact: true }).click();
  await expect(chart.getByRole("status")).toContainText("Showing stale chart from the last successful refresh");
  await expect(chart.locator("canvas").first()).toBeVisible();
  await page.getByRole("navigation", { name: "Saved conversations" }).getByRole("button", { name: /SPY/ }).click();
  await expect(page.getByText("Answer 1 about SPY; 1 questions in this conversation.")).toBeVisible();
});

test("reopened pending threads update without sending and removed history is cleared", async ({ page }) => {
  const fixture = await fixtureApp(page);
  await page.getByRole("button", { name: "Start conversation" }).click();
  const record = fixture.records.get("thread-1")!;
  const user: ConversationMessage = { id: "thread-1:pending-request", conversation_id: "thread-1", role: "user", message: "A previously submitted question", created_at: timestamp, status: "pending", error: null, citations: [], mode: null, cost_usd: 0, phase: null };
  record.messages.push(user);
  await page.reload();
  await page.getByRole("navigation", { name: "Saved conversations" }).getByRole("button", { name: /SPY/ }).click();
  await expect(page.getByText("Response pending", { exact: true })).toBeVisible();
  await page.getByLabel("Message about SPY", { exact: true }).fill("My next question");
  await expect(page.getByRole("button", { name: "Send", exact: true })).toBeDisabled();
  user.status = "complete";
  record.messages.push({ ...user, id: `${user.id}:answer`, role: "assistant", message: "The saved response has completed.", mode: "llm" });
  await expect(page.getByText("The saved response has completed.", { exact: true })).toBeVisible({ timeout: 8000 });
  await expect(page.getByRole("button", { name: "Send", exact: true })).toBeEnabled();
  expect(fixture.turns).toHaveLength(0);
  fixture.records.delete("thread-1");
  await expect(page.getByText("The saved response has completed.", { exact: true })).toHaveCount(0, { timeout: 8000 });
  await expect(page.getByRole("heading", { name: "A conversation, centered on a stock." })).toBeVisible();
});
