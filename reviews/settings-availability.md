# Passkey Settings and confidence availability review

## 1. Scope
Resolve the endless Settings loader and make unavailable confidence explicit. No authentication protocol or model training changes.

## 2. Hosted findings
September 11: Vercel serves commit 58604c9, while Render `/health` has no chat revision and both direct/proxied passkey status routes return 404. Authenticated `/models` reports `untrained`, zero registry entries and no promoted validated model. SPY chart retrieval also returned a sanitized Alpaca HTTP 504; this is separate from model availability.

## 3. Changes
Passkey loading now ends on failure, distinguishes outdated backend and expired session, and offers Retry. Disabled passkeys do not trigger credential-list requests. Recent signals and Settings explain why a calibrated percentage is unavailable and why later training does not score historical signals.

## 4. Tests
All six fixture browser regressions pass: 404 with successful retry, disabled configuration without listing, expired session, unavailable confidence, genuine 0%, and genuine 73%. The production Next build passes. The initial test selector collided with Next's route announcer; selectors now target the specific message. Source/artifact/history security and whitespace checks pass.

## 5. Contracts
Existing API/shared contracts remain. Python is authoritative for signal-time confidence; the frontend formats existing values without deriving probabilities.

## 6. Security
Hosted login was used only for read-only diagnosis and then logged out. No credentials were printed, no paid LLM call was made, and no training job was triggered. Existing private access and recovery remain.

## 7. Honesty
An updated frontend cannot supply a missing backend passkey route or create calibrated model confidence. Genuine zero scores remain visible as 0.0%; missing scores remain unavailable.

## 8. Deployment requirements
On the existing Render service, deploy the latest GitHub `main` commit and set `SELERY_PASSKEY_ORIGIN=https://selery-web.vercel.app` in Render's environment. Root `.env` does not propagate to Render. Confirm `/health` includes chat revision 2 and `/api/v1/auth/passkeys/status` returns 200. Then retry Settings and enroll. Numerical confidence separately requires sufficient suitable history, validated/calibrated model promotion and subsequent signal-time prediction capture; deployment alone is insufficient. Hardware Touch ID remains externally unverified.

## 9. Verdict
The UI defects pass focused acceptance. Hosted backend deployment, model qualification and physical Touch ID acceptance remain pending external work.
