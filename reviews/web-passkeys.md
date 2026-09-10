# Web passkey review

## 1. Scope

Implement web Touch ID through platform passkeys, with initial authenticated/password-confirmed enrollment, Open workspace login, cancellation/password recovery, and key removal. The user supplied `https://selery-web.vercel.app`. No native biometric work was integrated.

## 2. Runtime

FastAPI verifies WebAuthn through locked webauthn 2.8.0. Canonical Python contracts generate TypeScript schemas/client methods. Next uses native browser credential APIs and its existing backend proxy. Public keys persist in `auth_credentials` (migration 004). Pending challenges require one API process. No identity provider or paid integration was added.

## 3. Tests

Full Python suite: **266 passed**, 84% aggregate coverage and 99% passkey-module coverage; two existing test-client dependency deprecation warnings. All **15 Playwright tests passed**, including real signed registration/login through the Next proxy using Chromium's virtual platform authenticator. Web/native TypeScript checks and Next production build pass. Generated-contract parity and diff whitespace checks pass. The security scan passed over 241 authored files and 173 build artifacts plus Git history, without detected credential values or prohibited endpoint references.

Tests cover enrollment password/session proof, required user verification, wrong origin/RP/user handle, expired/replayed/browser-bound challenges, invalid signatures, counter reuse, legitimate zero-counter authenticators, credential removal/session invalidation, rate limits, malformed inputs and secure cookies. Browser tests cover enrollment, hidden password field after enrollment, HttpOnly session/token stripping, canceled prompt, fallback login and removal.

## 4. Data and causality

This change adds no quantitative calculations, provider requests or market-data transformations. Existing signal-confidence work is documented separately. Challenge expiry is two minutes; successful sessions last one hour. Restart invalidates pending ceremonies, not saved credentials.

## 5. Shared boundaries

Contracts and client methods are shared; browser serialization and settings remain in the web package. The OS owns private keys and biometric verification. Backend storage contains public keys and metadata only. Registration uses discoverable platform credentials; login requires verified device presence/user verification. Password remains the recovery path.

## 6. Security review

Independent review found a prune/consume interleaving that could resurrect a consumed challenge. A shared RLock now serializes pruning, consuming, throttling and enrollment count/existence/insertion; a deterministic paused-prune test and signed zero-counter replay regression cover it. Reviewer rechecked and cleared the blocker. Stored signature counters use conditional atomic updates. Exact origin/RP, session-bound enrollment, fresh password proof and browser-bound one-use challenges are enforced. Credential deletion invalidates sessions issued through that credential.

The first browser run exposed an unsuitable numeric-IP RP ID. Local and CI browser configuration now use localhost, and configuration rejects IP origins. Production uses the supplied HTTPS Vercel domain. Cryptographic behavior follows [py_webauthn registration](https://duo-labs.github.io/py_webauthn/registration.html) and [authentication](https://duo-labs.github.io/py_webauthn/authentication.html); credential/origin scoping follows [WebAuthn](https://www.w3.org/TR/webauthn-3/).

## 7. Honesty and permissions

No production environment, fingerprint, Apple account, provider API, paid model or billing setting was accessed. A virtual authenticator is evidence of the browser protocol and proxy integration, not physical Touch ID. Browser/OS fallback may use a device PIN. User-approved private access is retained.

## 8. Remaining work

Deploy updated web/backend code, set the exact Render origin, enroll on the public site and test real Touch ID/cancellation/recovery. Verify keys survive a hosted restart and database restore. Keep a single API process until ceremonies/limits move to shared atomic storage. Proxy egress sharing can temporarily exhaust the per-IP attempt limit. Password recovery and secure backups remain necessary; changing to another domain requires new enrollment.

## 9. Verdict

Local implementation and automated acceptance pass. The independent review blocker is resolved. Hosted configuration/deployment and physical-Mac acceptance remain pending; no claim of completion for those external checks.
