# Desktop conversation track

- The Assistant view now requires an explicit stock selection before creating a thread. The overview symbol is only a suggested value. Creation and chart refresh never dispatch analysis.
- Saved conversations are retrieved from the authenticated backend in pages of 50. Public-trader activity chat is unchanged.
- The desktop layout keeps the selected stock chart beside the scrollable conversation. Small screens stack the chart above the thread. Each conversation has its own chart interval and unsent draft while the view is mounted.
- Charts explicitly use IEX, show fixture/stale provenance, refresh every 30 seconds while the document is visible, and retain dated data after a refresh error. The interval is sent with new messages; the assistant is told that cursor/viewport state is not shared.
- Request IDs remain stable for uncertain delivery. Confirmed failed turns permit a fresh retry. A follow-up detail fetch can recover an answer after a transport error. Conversation-switch guards prevent late responses from crossing threads.
- Three deterministic browser tests intercept all API calls: stock gating/follow-ups/reopening/interval matching, failed response and retry, and delayed-response isolation plus stale chart retention. All three pass on isolated local port 3002. Web TypeScript checking passes.
- No live provider or LLM calls were made by this track. Cross-device behavior, backend integration, and real LLM quality require integration verification.
