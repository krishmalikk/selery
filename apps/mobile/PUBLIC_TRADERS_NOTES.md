# Public Traders native track

- Settings opens `/traders`, keeping the existing native tab bar unchanged. Activity details use `/public-activity/[id]`; chat accepts `activity_id`.
- Canonical shared models and client methods are owned by integration. This track changes only native screens and helpers.
- Public records are held only in current-screen memory, cleared on blur/background, and fetched again on focus. A network failure clears the prior records and displays an explicit offline limitation; these records never enter AsyncStorage.
- Directory/source filters and independent pagination are available. Activity filters cover trader, symbol and UTC opening-date boundaries. Date inputs reject impossible calendar dates and reversed ranges.
- Provider refresh is manual. Source status and availability control the refresh buttons. No records are treated as confirmed exits when they disappear.
- Source links require HTTPS, the selected provider's domain or a subdomain, no URL credentials, and no custom port. Synthetic records do not link to purported real trader profiles.
- Detail screens show provider identity, verification, instrument classification, all distinct timestamps, missing values, source limitations, and backend-calculated IEX reference movement. Market charts retain provenance and TradingView attribution.
- Activity-scoped chat retrieves evidence on the backend. On leaving/backgrounding chat, its explanation is cleared and late responses ignored. Local explanation remains available when the source disallows LLM use.

Validation: native TypeScript check passed against the integration branch's frozen contracts and installed Expo Router using a temporary external tsconfig. Bundle export and real iPhone interaction remain integration/device checks; no live provider or notification verification was performed in this track.
