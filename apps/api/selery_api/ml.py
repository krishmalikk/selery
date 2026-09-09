"""Point-in-time meta-labeling research; manual training with an untouched final holdout."""

import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import numpy as np
from selery_shared.indicators import atr, ema, rsi
from sklearn.calibration import calibration_curve
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sqlalchemy import insert
from sqlalchemy.exc import IntegrityError

from .model_registry import (
    FEATURE_NAMES,
    FEATURE_VERSION,
    eligible_model,
    load_artifact,
    promote_model,
    scope_for,
    scope_key,
)
from .outcomes import score_signal
from .storage import tables

VERSION = "meta-labels-2"
EMBARGO_SECONDS = 86400


def fractional_difference(values, d=0.4, window=30):
    """Fixed-width fractional differentiation; each output reads only its prefix."""
    if not 0 < d < 1 or window < 2:
        raise ValueError("d must be between zero and one; window >= 2")
    weights = [1.0]
    for k in range(1, window):
        weights.append(-weights[-1] * (d - k + 1) / k)
    output = np.full(len(values), np.nan)
    for i in range(window - 1, len(values)):
        output[i] = np.dot(weights, np.asarray(values[i - window + 1 : i + 1])[::-1])
    return output


def _known_bars(bars, symbol, feed, at, bar_time):
    known = sorted(
        [
            bar
            for bar in bars
            if bar.finalized
            and bar.symbol == symbol
            and bar.feed == feed
            and bar.available_at <= at
            and bar.time <= bar_time
        ],
        key=lambda bar: bar.time,
    )
    if len({bar.time for bar in known}) != len(known):
        raise ValueError("Duplicate bar timestamps require a versioned source revision before feature generation")
    return known


def _last_features(known):
    if len(known) < 31:
        return None
    close = [bar.close for bar in known]
    if min(close) <= 0:
        return None
    fast, slow, strength, volatility = ema(close, 9), ema(close, 21), rsi(close), atr(known)
    frac = fractional_difference(close)
    values = [
        (fast[-1] - slow[-1]) / close[-1],
        strength[-1] / 100,
        volatility[-1] / close[-1],
        close[-1] / close[-6] - 1,
        float(frac[-1]) / close[-1],
    ]
    return values if np.isfinite(values).all() else None


def feature_rows(bars):
    """Only finalized bars known at each row's availability may influence its features."""
    if len({(bar.symbol, bar.feed) for bar in bars}) > 1:
        raise ValueError("Feature rows require a single symbol and feed")
    rows = {}
    for bar in bars:
        if not bar.finalized:
            continue
        values = _last_features(_known_bars(bars, bar.symbol, bar.feed, bar.available_at, bar.time))
        if values is not None:
            rows[bar.time] = {"available_at": bar.available_at, "features": values}
    return rows


def signal_features(signal, bars):
    known = _known_bars(bars, signal.symbol, signal.feed, signal.available_at, signal.time)
    if not known or known[-1].time != signal.time:
        return None
    values = _last_features(known)
    if values is None:
        return None
    evidence = [[bar.time, bar.available_at, bar.open, bar.high, bar.low, bar.close] for bar in known]
    return {
        "features": values + [1.0 if signal.direction == "bullish" else -1.0],
        "available_at": signal.available_at,
        "scope": scope_for(signal),
        "signal_id": signal.id,
        "feature_version": FEATURE_VERSION,
        "source": "versioned-finalized-bar-contract",
        "source_digest": hashlib.sha256(json.dumps(evidence).encode()).hexdigest(),
    }


def save_feature_snapshot(store, signal, bars):
    snapshot = signal_features(signal, bars)
    if snapshot is None:
        return None
    identifier = hashlib.sha256(
        f"{scope_key(snapshot['scope'])}:{signal.id}:{signal.available_at}:{FEATURE_VERSION}".encode()
    ).hexdigest()
    snapshot["id"] = identifier
    table = tables["features"]
    try:
        with store.engine.begin() as conn:
            conn.execute(insert(table).values(id=identifier, created_at=datetime.now(UTC), payload=snapshot))
    except IntegrityError:
        prior = store.get("features", identifier)
        if prior != snapshot:
            raise ValueError("Signal-time feature snapshot changed; a source/feature revision is required")
    return snapshot


def meta_dataset(signals, bars, *, as_of=None, store=None):
    as_of = as_of or datetime.now(UTC)
    ordered = sorted(signals, key=lambda signal: (signal.available_at, signal.id))
    if len({signal.id for signal in ordered}) != len(ordered):
        raise ValueError("Duplicate signal identifiers are not independent training events")
    x, y, starts, ends = [], [], [], []
    for signal in ordered:
        if signal.available_at > as_of.timestamp():
            continue
        row = save_feature_snapshot(store, signal, bars) if store else signal_features(signal, bars)
        if not row:
            continue
        outcome = score_signal(signal, bars, now=as_of)
        if outcome.status not in ("target_first", "stop_first", "neither"):
            continue
        future = sorted(
            [
                bar
                for bar in bars
                if bar.finalized
                and bar.symbol == signal.symbol
                and bar.feed == signal.feed
                and bar.time >= signal.available_at
                and bar.available_at <= as_of.timestamp()
            ],
            key=lambda bar: bar.time,
        )
        label_end = outcome.resolved_at or (
            future[signal.horizon_bars - 1].available_at if len(future) >= signal.horizon_bars else None
        )
        if label_end is None:
            continue
        x.append(row["features"])
        y.append(int(outcome.status == "target_first"))
        starts.append(signal.available_at)
        ends.append(label_end)
    return (
        np.asarray(x, dtype=float).reshape(-1, len(FEATURE_NAMES)),
        np.asarray(y, dtype=int),
        np.asarray(starts),
        np.asarray(ends),
    )


def purged_walk_forward(starts, ends, n_splits=3, embargo_seconds=EMBARGO_SECONDS):
    starts, ends = np.asarray(starts), np.asarray(ends)
    if (
        starts.ndim != 1
        or ends.ndim != 1
        or len(starts) != len(ends)
        or n_splits < 1
        or embargo_seconds < 0
        or not np.isfinite(starts).all()
        or not np.isfinite(ends).all()
        or np.any(ends < starts)
        or np.any(np.diff(starts) < 0)
    ):
        raise ValueError("Events must be ordered with valid label intervals and nonnegative embargo")
    chunks = np.array_split(np.arange(len(starts)), n_splits + 1)
    for validation in chunks[1:]:
        if not len(validation):
            continue
        cutoff = starts[validation[0]] - embargo_seconds
        train = np.flatnonzero((starts < cutoff) & (ends < cutoff))
        yield train, validation


def reliability(y, probabilities):
    fraction, mean = calibration_curve(y, probabilities, n_bins=5, strategy="quantile")
    return [{"predicted": float(p), "observed": float(f)} for p, f in zip(mean, fraction)]


def _complex_model():
    try:
        from lightgbm import LGBMClassifier

        return LGBMClassifier(n_estimators=60, max_depth=3, num_leaves=7, verbosity=-1, random_state=42, n_jobs=1)
    except ImportError:
        return HistGradientBoostingClassifier(max_iter=60, max_depth=3, random_state=42)


def _baseline():
    return make_pipeline(StandardScaler(), LogisticRegression(max_iter=500, random_state=42))


def calibrate_oof(probabilities, labels):
    probabilities, labels = np.asarray(probabilities), np.asarray(labels)
    if len(probabilities) < 20 or len(np.unique(labels)) < 2 or not np.isfinite(probabilities).all():
        raise ValueError("Calibration needs finite out-of-fold probabilities and both label classes")
    return LogisticRegression(random_state=42).fit(probabilities.reshape(-1, 1), labels)


def fit_meta_dataset(x, y, starts, ends):
    """Fit/calibrate both fixed candidates on development data; evaluate final holdout once."""
    if len(y) < 120 or len(np.unique(y)) < 2:
        return {
            "status": "unavailable",
            "reason": f"Need at least 120 complete labeled events across both classes; found {len(y)}. No model was trained.",
            "version": VERSION,
        }, None
    if x.shape != (len(y), len(FEATURE_NAMES)) or not np.isfinite(x).all():
        raise ValueError("Feature matrix is invalid")
    list(purged_walk_forward(starts, ends))
    split = int(len(y) * 0.8)
    development = np.flatnonzero((np.arange(len(y)) < split) & (ends < starts[split] - EMBARGO_SECONDS))
    holdout = np.arange(split, len(y))
    if len(development) < 60 or len(np.unique(y[development])) < 2 or len(np.unique(y[holdout])) < 2:
        return {
            "status": "unavailable",
            "reason": "Insufficient purged development/final holdout events across both classes.",
        }, None
    xdev, ydev = x[development], y[development]
    folds, oof_prob, oof_base, oof_y = [], [], [], []
    for train, valid in purged_walk_forward(starts[development], ends[development]):
        if len(train) < 20 or len(np.unique(ydev[train])) < 2:
            continue
        baseline = _baseline().fit(xdev[train], ydev[train])
        model = _complex_model().fit(xdev[train], ydev[train])
        base, probs = baseline.predict_proba(xdev[valid])[:, 1], model.predict_proba(xdev[valid])[:, 1]
        folds.append(
            {
                "baseline_brier": float(brier_score_loss(ydev[valid], base)),
                "model_brier": float(brier_score_loss(ydev[valid], probs)),
                "train_events": len(train),
                "validation_events": len(valid),
                "latest_training_label": int(max(ends[development][train])),
                "validation_start": int(starts[development][valid[0]]),
            }
        )
        oof_prob.extend(probs)
        oof_base.extend(base)
        oof_y.extend(ydev[valid])
    if len(folds) < 3 or len(set(oof_y)) < 2:
        return {
            "status": "unavailable",
            "reason": "Three valid purged folds with both classes were not available.",
            "folds": folds,
        }, None
    calibrator = calibrate_oof(oof_prob, oof_y)
    baseline_calibrator = calibrate_oof(oof_base, oof_y)
    model, baseline = _complex_model().fit(xdev, ydev), _baseline().fit(xdev, ydev)
    probabilities = calibrator.predict_proba(model.predict_proba(x[holdout])[:, 1].reshape(-1, 1))[:, 1]
    base = baseline_calibrator.predict_proba(baseline.predict_proba(x[holdout])[:, 1].reshape(-1, 1))[:, 1]
    model_score, baseline_score = (
        float(brier_score_loss(y[holdout], probabilities)),
        float(brier_score_loss(y[holdout], base)),
    )
    stable = all(fold["model_brier"] <= fold["baseline_brier"] for fold in folds) and model_score < baseline_score
    metadata = {
        "status": "validated" if stable else "rejected",
        "validated": stable,
        "calibrated": True,
        "folds": folds,
        "holdout_brier": model_score,
        "baseline_holdout_brier": baseline_score,
        "reliability": reliability(y[holdout], probabilities),
        "baseline_reliability": reliability(y[holdout], base),
        "events": len(y),
        "holdout_events": len(holdout),
        "model": type(model).__name__,
        "baseline_model": "StandardScaler + LogisticRegression",
        "calibration": "Both candidates calibrated on past-only OOF probabilities; holdout labels excluded.",
        "reason": "Beat baseline in each raw fold and calibrated final holdout."
        if stable
        else "Did not beat baseline consistently; confidence remains unavailable.",
        "feature_names": FEATURE_NAMES,
        "feature_version": FEATURE_VERSION,
        "version": VERSION,
        "latest_label_at": int(max(ends)),
        "holdout_start": int(starts[split]),
    }
    artifact = {
        "model": model,
        "baseline": baseline,
        "calibrator": calibrator,
        "baseline_calibrator": baseline_calibrator,
        "feature_version": FEATURE_VERSION,
        "version": VERSION,
        "background": xdev[:100],
        "reference_features": xdev,
    }
    return metadata, artifact


def train_meta(signals, bars, store, artifact_dir, scope=None):
    if signals:
        inferred = scope_for(signals[0])
        if any(scope_for(signal) != inferred for signal in signals) or (scope is not None and scope != inferred):
            return {
                "status": "unavailable",
                "reason": "Training requires one matching symbol/feed/strategy/version/timeframe/horizon scope.",
            }
        scope = inferred
    trained_at = datetime.now(UTC)
    x, y, starts, ends = meta_dataset(signals, bars, as_of=trained_at, store=store)
    if len(y) < 120:
        return {
            "status": "unavailable",
            "reason": f"Need at least 120 complete labeled events across both classes; found {len(y)}. No model was trained.",
            "version": VERSION,
        }
    # Reserve this exact holdout before evaluation; concurrent/repeated manual tuning cannot silently reuse it.
    holdout_key = (
        "model-holdout:"
        + hashlib.sha256(json.dumps([scope, starts[int(len(y) * 0.8) :].tolist()]).encode()).hexdigest()
    )
    try:
        with store.engine.begin() as conn:
            conn.execute(
                insert(tables["settings"]).values(
                    id=holdout_key, created_at=trained_at, payload={"kind": "model_holdout_claim", "scope": scope}
                )
            )
            for event_at in set(starts[int(len(y) * 0.8) :].tolist()):
                conn.execute(
                    insert(tables["settings"]).values(
                        id=f"model-held-event:{scope_key(scope)}:{event_at}",
                        created_at=trained_at,
                        payload={"kind": "model_holdout_event", "scope": scope, "event_at": event_at},
                    )
                )
    except IntegrityError:
        return {
            "status": "unavailable",
            "reason": "This final holdout was already evaluated or claimed. New untouched observations are required.",
        }
    metadata, artifact = fit_meta_dataset(x, y, starts, ends)
    if artifact is None:
        return metadata
    identifier = uuid4().hex
    metadata.update(
        {
            "id": identifier,
            "scope": scope,
            "trained_at": datetime.now(UTC).isoformat(),
            "created_at": trained_at.isoformat(),
            "source": "versioned-finalized-bar-contract",
            "shap_status": "Computed on eligible inference only; optional dependency required.",
        }
    )
    if metadata["validated"]:
        import joblib

        target = Path(artifact_dir)
        target.mkdir(parents=True, exist_ok=True)
        artifact["scope"] = scope
        temporary, final = target / f".{identifier}.tmp", target / f"{identifier}.joblib"
        joblib.dump(artifact, temporary)
        os.replace(temporary, final)
        metadata["artifact_sha256"] = hashlib.sha256(final.read_bytes()).hexdigest()
    store.put("models", metadata, identifier, immutable=True)
    if metadata["validated"]:
        metadata["status"] = "champion" if promote_model(store, metadata) else "validated"
        store.put("models", metadata, identifier)
    store.audit("manual_model_research", {"id": identifier, "status": metadata["status"]})
    return metadata


def predict_signal(signal, bars, store, artifact_dir):
    if signal.available_at > datetime.now(UTC).timestamp():
        return {
            "confidence": None,
            "reason": "Signal availability is in the future.",
            "model_id": None,
            "shap": None,
            "shap_reason": "No point-in-time prediction available.",
        }
    metadata, reason = eligible_model(store, signal)
    unavailable = {
        "confidence": None,
        "reason": reason,
        "model_id": None,
        "shap": None,
        "shap_reason": "No eligible calibrated model.",
    }
    if metadata is None:
        return unavailable
    try:
        snapshot = save_feature_snapshot(store, signal, bars)
    except ValueError:
        return {**unavailable, "reason": "Signal-time feature inputs differ from their immutable snapshot."}
    if snapshot is None:
        return {**unavailable, "reason": "Insufficient finalized bars known at signal time."}
    try:
        artifact = load_artifact(metadata, artifact_dir)
        row = np.asarray([snapshot["features"]])
        raw = artifact["model"].predict_proba(row)[:, 1]
        probability = float(artifact["calibrator"].predict_proba(raw.reshape(-1, 1))[0, 1])
        if not np.isfinite(probability) or not 0 <= probability <= 1:
            raise ValueError("Invalid calibrated probability")
    except (OSError, ValueError, KeyError, TypeError, ImportError):
        return {**unavailable, "reason": "Validated model artifact is unavailable or incompatible."}
    result = {
        "confidence": probability,
        "reason": None,
        "model_id": metadata["id"],
        "scope": metadata["scope"],
        "feature_version": FEATURE_VERSION,
        "shap": None,
        "shap_reason": "Optional SHAP dependency unavailable.",
    }
    try:
        import shap

        def calibrated(values):
            return artifact["calibrator"].predict_proba(artifact["model"].predict_proba(values)[:, 1].reshape(-1, 1))[
                :, 1
            ]

        explainer = shap.Explainer(calibrated, artifact["background"], algorithm="permutation", seed=42)
        explanation = explainer(row, max_evals=2 * len(FEATURE_NAMES) + 1)
        values = np.asarray(explanation.values).reshape(-1)
        if len(values) != len(FEATURE_NAMES) or not np.isfinite(values).all():
            raise ValueError("Invalid SHAP explanation")
        result["shap"] = {
            "values": dict(zip(FEATURE_NAMES, map(float, values))),
            "base_value": float(np.asarray(explanation.base_values).reshape(-1)[0]),
            "output": "calibrated target-first probability",
            "background": "development features only",
        }
        result["shap_reason"] = None
    except ImportError:
        pass
    except (ValueError, TypeError, RuntimeError, AttributeError):
        result["shap_reason"] = (
            "SHAP could not explain this validated artifact; confidence remains independently calibrated."
        )
    return result


def drift_score(reference, current):
    reference, current = np.asarray(reference), np.asarray(current)
    if not len(reference) or not len(current) or not np.isfinite(reference).all() or not np.isfinite(current).all():
        return None
    edges = np.unique(np.quantile(reference, np.linspace(0, 1, 6)))
    if len(edges) < 3:
        return None
    edges[0], edges[-1] = -np.inf, np.inf
    a = np.maximum(np.histogram(reference, edges)[0] / len(reference), 1e-6)
    b = np.maximum(np.histogram(current, edges)[0] / len(current), 1e-6)
    return float(np.sum((b - a) * np.log(b / a)))


def sequence_model(input_features, kind="lstm"):
    """Optional sequence architecture; the same purged evaluator must qualify it before use."""
    import torch
    from torch import nn

    if kind not in ("lstm", "gru", "transformer"):
        raise ValueError("Unknown sequence architecture")

    class SequenceMeta(nn.Module):
        def __init__(self):
            super().__init__()
            self.input = nn.Linear(input_features, 32)
            self.encoder = (
                nn.TransformerEncoder(
                    nn.TransformerEncoderLayer(d_model=32, nhead=4, batch_first=True, dropout=0), num_layers=1
                )
                if kind == "transformer"
                else (nn.LSTM if kind == "lstm" else nn.GRU)(32, 32, batch_first=True)
            )
            self.head = nn.Linear(32, 1)
            self.position = nn.Parameter(torch.zeros(1, 512, 32)) if kind == "transformer" else None

        def forward(self, x):
            if x.shape[1] > 512:
                raise ValueError("Sequence length exceeds 512 observations")
            embedded = self.input(x)
            if self.position is not None:
                embedded = embedded + self.position[:, : x.shape[1]]
            if kind == "transformer":
                length = x.shape[1]
                mask = torch.triu(torch.ones(length, length, device=x.device, dtype=torch.bool), diagonal=1)
                encoded = self.encoder(embedded, mask=mask)
            else:
                encoded, _ = self.encoder(embedded)
            return self.head(encoded[:, -1]).squeeze(-1)

    return SequenceMeta()


def validate_sequence(x, y, starts, ends, kind="lstm", epochs=10, available_at=None):
    """Optional manual sequence experiment on the same past-only purged folds.

    No registry promotion or confidence follows from this diagnostic. Each sequence
    must end at its event timestamp; callers supply point-in-time windows.
    """
    try:
        import torch
    except ImportError:
        return {"status": "unavailable", "reason": "Optional PyTorch dependency is not installed."}
    x, y = np.asarray(x, dtype=np.float32), np.asarray(y)
    if x.ndim != 3 or len(x) != len(y) or len(y) < 120 or not np.isfinite(x).all() or not 1 <= epochs <= 100:
        return {
            "status": "unavailable",
            "reason": "Need at least 120 finite event-aligned sequences and 1–100 manual epochs.",
        }
    timestamps = np.asarray(available_at) if available_at is not None else None
    if (
        timestamps is None
        or timestamps.shape != x.shape[:2]
        or not np.isfinite(timestamps).all()
        or np.any(timestamps > np.asarray(starts)[:, None])
        or np.any(np.diff(timestamps, axis=1) < 0)
    ):
        return {
            "status": "unavailable",
            "reason": "Each sequence needs ordered availability timestamps no later than its signal.",
        }
    cutoff = int(len(y) * 0.8)
    development = np.flatnonzero((np.arange(len(y)) < cutoff) & (np.asarray(ends) < starts[cutoff] - EMBARGO_SECONDS))
    folds = []
    for train, valid in purged_walk_forward(np.asarray(starts)[development], np.asarray(ends)[development]):
        if len(train) < 20 or len(np.unique(y[development][train])) < 2:
            continue
        train, valid = development[train], development[valid]
        scaler = StandardScaler().fit(x[train].reshape(-1, x.shape[-1]))
        inputs = torch.tensor(scaler.transform(x[train].reshape(-1, x.shape[-1])).reshape(x[train].shape))
        validation = torch.tensor(scaler.transform(x[valid].reshape(-1, x.shape[-1])).reshape(x[valid].shape))
        torch.manual_seed(42)
        model = sequence_model(x.shape[-1], kind)
        optimizer = torch.optim.Adam(model.parameters(), lr=0.001)
        labels = torch.tensor(y[train], dtype=torch.float32)
        for _ in range(epochs):
            optimizer.zero_grad()
            loss = torch.nn.functional.binary_cross_entropy_with_logits(model(inputs), labels)
            loss.backward()
            optimizer.step()
        model.eval()
        with torch.no_grad():
            probabilities = torch.sigmoid(model(validation)).numpy()
        baseline = _baseline().fit(x[train, -1], y[train])
        folds.append(
            {
                "sequence_brier": float(brier_score_loss(y[valid], probabilities)),
                "baseline_brier": float(brier_score_loss(y[valid], baseline.predict_proba(x[valid, -1])[:, 1])),
                "train_events": len(train),
                "validation_events": len(valid),
            }
        )
    return {
        "status": "research_only" if len(folds) == 3 else "unavailable",
        "architecture": kind,
        "folds": folds,
        "reason": "Sequence fold research only; calibration and untouched final-holdout qualification are still required. No confidence is exposed.",
        "holdout_events_untouched": len(y) - cutoff,
    }
