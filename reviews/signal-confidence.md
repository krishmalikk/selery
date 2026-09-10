# Signal-confidence display review

## 1. Scope

Recent web signals and native signal cards/details explicitly display an original calibrated percentage or Unavailable. This change does not train a model, remove authentication, or implement the proposed chat roadmap.

## 2. Runtime

Both clients consume the same presentation helper and existing Signal contract. The API explains why a chart signal has no saved prediction. No hosted configuration or data was changed.

The Next.js production build and both iOS/Android exports passed after integration. These are compilation/bundling checks, not browser or physical-device acceptance.

## 3. Tests

All 27 API/model-registry tests pass, including added cases for preserving 0% and nonzero original estimates and rejecting a saved estimate from a different horizon. Web and native TypeScript checks pass. The new tests exercise propagation of a synthetic saved prediction; they are not evidence of real predictive performance.

## 4. Lookahead

Charts reuse immutable signal-time snapshots only when symbol/feed/strategy/version/timeframe/horizon match. Missing historical predictions remain unavailable; no present-day model is applied retroactively.

## 5. Shared code

Python owns predictions and model eligibility. The shared TypeScript helper only formats existing probabilities and describes their meaning; it does not calculate confidence from indicators or ask the LLM for a score. No contract generation change is needed.

## 6. Security

Existing authentication, provider-secret handling and LLM budget checks remain. No training job, live model request or external message was sent. Local model/status inspection printed counts only.

## 7. Honesty

The score estimates target reached before stop within the stated horizon, rather than probability of profit. Training excludes ambiguous/incomplete outcomes. The local database contained zero models and zero stored signals at inspection; the Render database was not inspected. Null values and invalid numeric values remain unavailable in presentation.

## 8. Remaining work

Numeric confidence requires sufficient labeled history, validation/calibration, an eligible model and forward signal capture. Inspect calibration reliability and sample sizes, and expose model/version provenance alongside confidence in a future iteration. Native physical-device presentation remains unverified. The assistant roadmap is in ../docs/CHAT-IMPROVEMENTS.md.

## 9. Verdict

The implemented display and original-score propagation pass focused local checks. Real-market model qualification, hosted deployment and physical-device acceptance remain pending.
