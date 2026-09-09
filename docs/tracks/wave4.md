# Wave 4 — scoped, point-in-time model research

## Implemented

Manual meta-label training now records symbol, feed, timeframe, strategy/version and horizon scope; feature version; training/activation timestamps; latest label availability; calibrated logistic baseline and complex-model comparison; fold/holdout evidence; and a SHA-256 artifact checksum. LightGBM is used when installed, otherwise the reported estimator is HistGradientBoosting. Standardization is fitted inside baseline training folds. Both candidates are calibrated using only past-fold out-of-fold predictions; the final holdout never fits a model, scaler, or calibrator. Holdout observations are atomically claimed, preventing concurrent or later manual runs from silently reusing overlapping final holdouts.

Features use only finalized bars available by each signal's timestamp. Late and unfinalized historical bars cannot influence earlier feature vectors. Signal-time feature snapshots include source digest, scope and feature version; an attempted rewrite with different inputs is refused. Ambiguous/incomplete outcomes remain excluded from labels. Dataset events are ordered and duplicate signal IDs are rejected.

`predict_signal(signal, bars, store, artifact_dir)` returns `confidence`, `reason`, `model_id`, optional scope/feature version, and optional `shap`/`shap_reason`. Predictions require the active champion's exact scope, calibrated validation, matching feature version, checksum-verified local artifact, and training, label and activation timestamps no later than signal availability. Future signals and historical signals preceding model deployment receive no confidence. Provider/source identity beyond the typed Bar contract is not available in this API; snapshots disclose that source limitation rather than claiming additional provenance.

SHAP, when installed, evaluates the actual calibrated probability function against development-only background features using a permutation explainer. Values, base value, output meaning and background provenance are returned. Missing or incompatible optional dependencies produce an explicit explanation reason, never synthetic SHAP values.

## Registry and drift

`model_registry.registry_models(store)` derives displayed active status from the atomic scope champion pointer. Use this instead of trusting a model record's historical status string. `promote_model` requires validated/calibrated artifact metadata and replaces a scope champion only with newer label/training evidence. Atomic compare-and-swap prevents stale concurrent completion from overriding a newer candidate.

`drift_decision(reference, current)` is a pure population-stability-index policy with fixed reference bins, a minimum of 100 finite observations and a default threshold of 0.25. It returns retain/rollback/unavailable; the threshold is a research policy, not proof of model failure. `rollback_champion(store, scope, decision)` is an explicit action: quarantine the drifted model, restore a prior compatible validated candidate if available, otherwise disable confidence. Quarantined models cannot be automatically re-promoted or toggled back by successive rollbacks. No periodic training or rollback scheduler is enabled.

## Optional sequence research

LSTM, GRU and causally masked Transformer architectures are provided. The Transformer includes position parameters; windows are limited to 512 observations. `validate_sequence(x, y, starts, ends, kind, epochs, available_at)` requires timestamped sequences known by each event, fits scalers on each training fold, and compares actual fold predictions with a logistic baseline using the same purge/embargo rules. It intentionally leaves the final 20% holdout untouched and cannot promote a model or expose confidence: sequence calibration and independent final-holdout qualification remain pending.

## Integration and verification

The existing `train_meta(signals, bars, store, artifact_dir, scope=None)` remains compatible; optional scope must match the inferred signal scope. Root API can attach `confidence` and `reason` from `predict_signal` to newly observed signal responses and expose SHAP separately after generated-contract updates. Invoke inference through `asyncio.to_thread` when called from async routes because model/SHAP work is synchronous. Do not attach today's model to historical chart signals. Use `registry_models` for `/models` metadata.

Deterministic tests cover future-data mutation, late/unfinalized bars, immutable features, scope and time gates, checksum tampering, empirical calibration, final-holdout mutation invariance, overlapping holdout claims, champion rollback/quarantine, drift sufficiency, and explicit optional-dependency absence. The architecture gradient tests skip when PyTorch is unavailable. No market performance, promoted production model, SHAP availability on a deployed model, or sequence qualification is claimed without its validation evidence.
