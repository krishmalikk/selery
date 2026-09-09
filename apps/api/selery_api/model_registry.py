"""Versioned, scope-specific model selection with atomic promotion and explicit rollback."""

import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import insert, select, update
from sqlalchemy.exc import IntegrityError

from .storage import tables

FEATURE_VERSION = "price-features-2"
FEATURE_NAMES = ["ema_gap", "rsi", "atr_fraction", "lagged_price_change", "fractional_difference", "signal_direction"]
SCOPE_FIELDS = ("symbol", "feed", "timeframe", "strategy", "strategy_version", "horizon_bars")


def scope_for(signal):
    return {
        key: getattr(signal, key).value if hasattr(getattr(signal, key), "value") else getattr(signal, key)
        for key in SCOPE_FIELDS
    }


def scope_key(scope):
    return hashlib.sha256(json.dumps({key: scope[key] for key in SCOPE_FIELDS}, sort_keys=True).encode()).hexdigest()


def timestamp(value):
    if isinstance(value, (float, int)):
        return float(value)
    return datetime.fromisoformat(value).timestamp()


def registry_entry(store, scope):
    return store.get("settings", "model-champion:" + scope_key(scope))


def _set_pointer(store, scope, candidate, reason, expected_id=None):
    """Compare-and-swap works for both SQLite and PostgreSQL JSON-backed stores."""
    table = tables["settings"]
    identifier = "model-champion:" + scope_key(scope)
    for _ in range(5):
        with store.engine.begin() as connection:
            row = connection.execute(
                select(table.c.payload, table.c.created_at).where(table.c.id == identifier)
            ).first()
            previous = row[0] if row else None
            if expected_id is not None and (previous or {}).get("model_id") != expected_id:
                return False
            if previous and reason == "validated_promotion":
                existing = store.get("models", previous["model_id"]) if previous.get("model_id") else None
                if existing and (existing["latest_label_at"], timestamp(existing["trained_at"])) >= (
                    candidate["latest_label_at"],
                    timestamp(candidate["trained_at"]),
                ):
                    return False
            payload = {
                "scope": scope,
                "model_id": candidate["id"] if candidate else None,
                "previous_id": (previous or {}).get("model_id"),
                "activated_at": datetime.now(UTC).isoformat(),
                "reason": reason,
            }
            if row:
                result = connection.execute(
                    update(table)
                    .where(table.c.id == identifier, table.c.created_at == row[1])
                    .values(payload=payload, created_at=datetime.now(UTC))
                )
                if result.rowcount == 1:
                    return True
            else:
                try:
                    connection.execute(
                        insert(table).values(id=identifier, payload=payload, created_at=datetime.now(UTC))
                    )
                    return True
                except IntegrityError:
                    pass
    return False


def promote_model(store, metadata):
    if store.get("settings", "model-disabled:" + metadata["id"]):
        return False
    if (
        not metadata.get("validated")
        or not metadata.get("calibrated")
        or not metadata.get("artifact_sha256")
        or metadata.get("feature_version") != FEATURE_VERSION
        or metadata["latest_label_at"] > timestamp(metadata["trained_at"])
        or timestamp(metadata["trained_at"]) > datetime.now(UTC).timestamp()
    ):
        return False
    promoted = _set_pointer(store, metadata["scope"], metadata, "validated_promotion")
    if promoted:
        store.audit("model_promoted", {"id": metadata["id"], "scope": metadata["scope"]})
    return promoted


def eligible_model(store, signal):
    scope = scope_for(signal)
    pointer = registry_entry(store, scope)
    if not pointer or not pointer.get("model_id"):
        return None, "No active validated model for this symbol/feed/strategy/timeframe/horizon."
    metadata = store.get("models", pointer["model_id"])
    if metadata and store.get("settings", "model-disabled:" + metadata["id"]):
        return None, "Model is quarantined after a drift rollback."
    if not metadata or metadata.get("scope") != scope or metadata.get("feature_version") != FEATURE_VERSION:
        return None, "Model scope or feature version does not match this signal."
    if not metadata.get("validated") or not metadata.get("calibrated"):
        return None, "Model has not passed validation and calibration."
    if (
        timestamp(metadata["trained_at"]) > signal.available_at
        or metadata["latest_label_at"] > signal.available_at
        or timestamp(pointer["activated_at"]) > signal.available_at
    ):
        return None, "Model training, labels, or activation postdate this signal; historical confidence is unavailable."
    return metadata, None


def load_artifact(metadata, artifact_dir):
    import joblib

    if not re.fullmatch(r"[a-f0-9]{32}", metadata["id"]):
        raise ValueError("Invalid model identifier")
    target = Path(artifact_dir) / f"{metadata['id']}.joblib"
    if not target.is_file() or target.is_symlink():
        raise ValueError("Model artifact unavailable")
    if hashlib.sha256(target.read_bytes()).hexdigest() != metadata.get("artifact_sha256"):
        raise ValueError("Model artifact checksum mismatch")
    artifact = joblib.load(target)
    if artifact.get("feature_version") != FEATURE_VERSION or artifact.get("scope") != metadata["scope"]:
        raise ValueError("Artifact scope/version mismatch")
    return artifact


def drift_decision(reference, current, *, min_events=100, threshold=0.25):
    """Pure diagnostic; PSI threshold is a research policy, not proof of model failure."""
    import numpy as np

    from .ml import drift_score

    reference, current = np.asarray(reference), np.asarray(current)
    if reference.ndim != 2 or current.ndim != 2 or reference.shape[1] != current.shape[1]:
        return {"action": "unavailable", "reason": "Feature matrix dimensions do not match."}
    if (
        len(reference) < min_events
        or len(current) < min_events
        or not np.isfinite(reference).all()
        or not np.isfinite(current).all()
    ):
        return {
            "action": "unavailable",
            "reason": "Need sufficient finite reference and matured current feature observations.",
        }
    scores = [drift_score(reference[:, index], current[:, index]) for index in range(reference.shape[1])]
    valid = [score for score in scores if score is not None]
    if not valid:
        return {"action": "unavailable", "reason": "Reference features do not support stable histogram bins."}
    return {
        "action": "rollback" if max(valid) > threshold else "retain",
        "psi": scores,
        "threshold": threshold,
        "reason": "Reference-bin feature drift policy; no outcome-performance claim.",
    }


def rollback_champion(store, scope, decision):
    """Explicit invocation only. A drifted model is deactivated; an eligible prior model may resume."""
    if decision.get("action") != "rollback":
        return {"changed": False, "reason": decision.get("reason", "Rollback was not requested.")}
    pointer = registry_entry(store, scope)
    if not pointer or not pointer.get("model_id"):
        return {"changed": False, "reason": "No active champion."}
    previous = store.get("models", pointer.get("previous_id")) if pointer.get("previous_id") else None
    if previous and store.get("settings", "model-disabled:" + previous["id"]):
        previous = None
    if previous and (
        previous.get("scope") != scope
        or not previous.get("validated")
        or not previous.get("calibrated")
        or previous.get("feature_version") != FEATURE_VERSION
    ):
        previous = None
    store.put(
        "settings",
        {"kind": "model_quarantine", "model_id": pointer["model_id"], "reason": decision},
        "model-disabled:" + pointer["model_id"],
        immutable=True,
    )
    changed = _set_pointer(store, scope, previous, "feature_drift_rollback", expected_id=pointer["model_id"])
    if changed:
        store.audit(
            "model_rollback",
            {"from": pointer["model_id"], "to": previous["id"] if previous else None, "decision": decision},
        )
    return {
        "changed": changed,
        "model_id": previous["id"] if changed and previous else None,
        "reason": "Previous validated model restored."
        if previous
        else "Confidence disabled pending validated replacement.",
    }


def registry_models(store):
    """Derive active status from the authoritative pointer, never stale model-record labels."""
    result = []
    for model in store.list("models", 10000):
        scope = model.get("scope")
        pointer = registry_entry(store, scope) if scope else None
        quarantined = bool(store.get("settings", "model-disabled:" + model["id"]))
        active = bool(pointer and pointer.get("model_id") == model["id"] and not quarantined)
        result.append(
            {
                **model,
                "status": "quarantined"
                if quarantined
                else "champion"
                if active
                else "validated"
                if model.get("validated")
                else model.get("status", "unavailable"),
            }
        )
    return result
