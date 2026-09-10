# Web chat improvements

The web conversation and Public Traders answer surfaces use the shared restricted Markdown parser and React text nodes. Inline known evidence IDs open provider/feed/observation/availability cards; unknown IDs remain visibly unknown. Only absolute HTTP(S) source links are enabled. Old stored answers without enriched evidence metadata explicitly show unavailable fields.

Conversation GET polling continues every 700 ms while the POST or saved assistant is pending, exposing actual backend text and retrieval/generation phases. Idle visible threads retain five-second polling; hidden tabs resume on visibility changes. Stop display freezes output only; Resume display reveals the saved response and never sends another generation request. The UI explains that the request continues and can still cost money. Existing request IDs, locks, draft retention and auth/history clearing remain.

Search uses the backend query and rejects late list responses. Rename and explicit history summarization update the saved thread; summaries are labeled extracted conversation history, not market evidence. They do not request a model.

Ask about this signal creates a dedicated conversation with the selected immutable ID, timeframe and chart range ending at the signal bar. Reopened signal threads fetch their server-persisted chart snapshot, filter to its dates, retain the original marker, and disable timeframe switching. A marker in an ordinary conversation can also start a new signal thread. Creating a thread never requests paid analysis.

Validation: web TypeScript check passed. Seven deterministic Chromium checks cover the three new improvement flows and four existing conversation regression flows: streaming during pending POST, stop/resume without duplicate submission, hostile Markdown, evidence cards/unknown references, search/rename/summary attribution, dated signal range/timeframe locking, followups, failed requests, late responses, reconnect, and removed history. These are fixture checks, not live provider/deployment acceptance.

Integration dependency: the shared research-markdown parser from the native track and root-owned conversationChart API method/contracts. No backend or shared contract edits are included in this track commit. Real hosted deployment verification belongs to integration. Web Touch ID remains independent of chat changes.
