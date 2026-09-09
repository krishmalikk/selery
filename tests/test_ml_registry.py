import hashlib
from datetime import UTC, datetime

import joblib
import numpy as np
import pytest
from selery_api.ml import (
    FEATURE_NAMES,
    calibrate_oof,
    feature_rows,
    fit_meta_dataset,
    predict_signal,
    save_feature_snapshot,
    sequence_model,
    signal_features,
    train_meta,
    validate_sequence,
)
from selery_api.model_registry import (
    FEATURE_VERSION,
    drift_decision,
    eligible_model,
    promote_model,
    registry_entry,
    rollback_champion,
    scope_for,
)
from selery_api.storage import Store
from selery_shared.models import Bar, Feed, Signal, Timeframe
from sklearn.linear_model import LogisticRegression


@pytest.fixture
def store():
    result = Store("sqlite:///:memory:")
    yield result
    result.engine.dispose()


def data(at=1_700_000_000):
    bars = [
        Bar(
            symbol="SPY",
            time=at + i * 300,
            available_at=at + (i + 1) * 300,
            open=100 + i / 10,
            close=100 + i / 10,
            high=101 + i / 10,
            low=99 + i / 10,
            feed=Feed.IEX,
        )
        for i in range(50)
    ]
    last = bars[-1]
    signal = Signal(
        id="test",
        symbol="SPY",
        time=last.time,
        available_at=last.available_at,
        strategy="ema_cross",
        strategy_version="1",
        timeframe=Timeframe.M5,
        direction="bullish",
        reference_price=last.close,
        stop=last.close - 2,
        target=last.close + 2,
        horizon_bars=2,
        feed=Feed.IEX,
        explanation="test",
    )
    return signal, bars


def metadata(signal, identifier="a" * 32, at=None):
    return {
        "id": identifier,
        "scope": scope_for(signal),
        "validated": True,
        "calibrated": True,
        "feature_version": FEATURE_VERSION,
        "trained_at": datetime.fromtimestamp(at or signal.available_at - 500, UTC).isoformat(),
        "latest_label_at": signal.available_at - 1000,
        "artifact_sha256": "placeholder",
    }


def test_late_and_unfinalized_bars_cannot_leak_into_signal_features():
    signal, bars = data()
    expected = signal_features(signal, bars)
    future = bars[-1].model_copy(
        update={"time": signal.available_at, "available_at": signal.available_at + 300, "close": 100000}
    )
    assert signal_features(signal, bars + [future]) == expected
    revised = bars[5].model_copy(update={"available_at": signal.available_at + 100, "close": 100000})
    assert signal_features(signal, bars[:5] + [revised] + bars[6:]) == signal_features(signal, bars[:5] + bars[6:])
    nonfinal = bars[5].model_copy(update={"finalized": False, "close": 100000})
    assert signal_features(signal, bars[:5] + [nonfinal] + bars[6:]) == signal_features(signal, bars[:5] + bars[6:])
    changed_future = future.model_copy(update={"close": 200000})
    assert feature_rows(bars + [future])[bars[40].time] == feature_rows(bars + [changed_future])[bars[40].time]


def test_feature_snapshots_immutable_and_versioned(store):
    signal, bars = data()
    first = save_feature_snapshot(store, signal, bars)
    assert save_feature_snapshot(store, signal, bars) == first
    assert first["feature_version"] == FEATURE_VERSION and first["scope"]["feed"] == "iex"
    modified = bars[:-1] + [bars[-1].model_copy(update={"close": bars[-1].close + 0.5})]
    with pytest.raises(ValueError, match="snapshot changed"):
        save_feature_snapshot(store, signal, modified)
    assert len(store.list("features")) == 1


def test_scope_and_temporal_gates(store):
    signal, _ = data(int(datetime.now(UTC).timestamp()) - 16_000)
    model = metadata(signal)
    store.put("models", model, model["id"])
    assert promote_model(store, model)
    assert eligible_model(store, signal)[0] is None  # Activation happened after this historical signal.
    later = signal.model_copy(update={"available_at": int(datetime.now(UTC).timestamp()) + 10})
    assert eligible_model(store, later)[0]["id"] == model["id"]
    assert eligible_model(store, later.model_copy(update={"feed": Feed.SIP}))[0] is None
    assert eligible_model(store, later.model_copy(update={"horizon_bars": 12}))[0] is None
    changed = {**model, "trained_at": datetime.fromtimestamp(later.available_at + 100, UTC).isoformat()}
    store.put("models", changed, model["id"])
    assert eligible_model(store, later)[0] is None


def test_registry_promotion_and_rollback_do_not_reenable_quarantined_models(store):
    signal, _ = data(int(datetime.now(UTC).timestamp()) - 16_000)
    first, second = metadata(signal, "a" * 32), metadata(signal, "b" * 32, signal.available_at - 100)
    for model in (first, second):
        store.put("models", model, model["id"])
        assert promote_model(store, model)
    assert registry_entry(store, scope_for(signal))["model_id"] == second["id"]
    assert not promote_model(store, first)  # A stale concurrent training completion cannot replace the newer model.
    assert rollback_champion(store, scope_for(signal), {"action": "rollback"})["model_id"] == first["id"]
    assert not promote_model(store, second)
    assert rollback_champion(store, scope_for(signal), {"action": "rollback"})["model_id"] is None
    assert registry_entry(store, scope_for(signal))["model_id"] is None


def test_calibration_learns_empirical_probabilities_not_a_fabricated_score():
    probabilities = np.repeat([0.1, 0.9], 200)
    labels = np.r_[np.tile([0, 0, 0, 1], 50), np.tile([1, 1, 1, 0], 50)]
    calibrated = calibrate_oof(probabilities, labels).predict_proba(np.array([[0.1], [0.9]]))[:, 1]
    assert calibrated[0] == pytest.approx(0.25, abs=0.05)
    assert calibrated[1] == pytest.approx(0.75, abs=0.05)
    assert np.mean((calibrated[np.repeat([0, 1], 200)] - labels) ** 2) < np.mean((probabilities - labels) ** 2)


def synthetic_dataset():
    rng = np.random.default_rng(20)
    x = rng.normal(size=(600, len(FEATURE_NAMES)))
    y = (x[:, 0] * x[:, 1] > 0).astype(int)
    starts = np.arange(len(y)) * 172800 + 1_500_000_000
    return x, y, starts, starts + 300


def test_holdout_mutation_does_not_change_fitted_models_or_calibrators():
    x, y, starts, ends = synthetic_dataset()
    report, artifact = fit_meta_dataset(x, y, starts, ends)
    changed = y.copy()
    changed[int(len(y) * 0.8) :] = 1 - changed[int(len(y) * 0.8) :]
    altered, second = fit_meta_dataset(x, changed, starts, ends)
    assert artifact is not None and second is not None
    assert np.array_equal(artifact["model"].predict_proba(x[:30]), second["model"].predict_proba(x[:30]))
    assert np.array_equal(artifact["calibrator"].coef_, second["calibrator"].coef_)
    assert np.array_equal(artifact["baseline_calibrator"].coef_, second["baseline_calibrator"].coef_)
    assert report["holdout_brier"] != altered["holdout_brier"]
    assert all(fold["latest_training_label"] < fold["validation_start"] - 86400 for fold in report["folds"])


def test_repeated_or_overlapping_final_holdout_is_refused(store, monkeypatch, tmp_path):
    from selery_api import ml

    signal, bars = data()
    monkeypatch.setattr(ml, "meta_dataset", lambda *args, **kwargs: synthetic_dataset())
    first = train_meta([signal], bars, store, tmp_path)
    assert first["status"] in ("champion", "rejected", "validated")
    assert "already evaluated" in train_meta([signal], bars, store, tmp_path)["reason"]
    dataset = synthetic_dataset()
    monkeypatch.setattr(ml, "meta_dataset", lambda *args, **kwargs: tuple(value[1:] for value in dataset))
    assert "already evaluated" in train_meta([signal], bars, store, tmp_path)["reason"]


def test_inference_checks_hash_scope_calibration_and_shap_absence(store, tmp_path, monkeypatch):
    import sys

    signal, bars = data(int(datetime.now(UTC).timestamp()) - 15_100)
    model = metadata(signal)
    x = np.array([[0] * 6, [1] * 6, [2] * 6, [3] * 6])
    y = np.array([0, 0, 1, 1])
    classifier = LogisticRegression().fit(x, y)
    calibrator = LogisticRegression().fit(np.array([[0.1], [0.2], [0.8], [0.9]]), y)
    artifact = {
        "model": classifier,
        "calibrator": calibrator,
        "scope": scope_for(signal),
        "feature_version": FEATURE_VERSION,
        "background": x,
    }
    path = tmp_path / f"{model['id']}.joblib"
    joblib.dump(artifact, path)
    model["artifact_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    store.put("models", model, model["id"])
    assert promote_model(store, model)
    pointer = registry_entry(store, scope_for(signal))
    pointer["activated_at"] = model["trained_at"]
    from selery_api.model_registry import scope_key

    store.put("settings", pointer, "model-champion:" + scope_key(scope_for(signal)))
    monkeypatch.setitem(sys.modules, "shap", None)
    prediction = predict_signal(signal, bars, store, tmp_path)
    assert 0 <= prediction["confidence"] <= 1
    assert prediction["shap"] is None and "dependency" in prediction["shap_reason"]
    path.write_bytes(b"corrupt")
    assert predict_signal(signal, bars, store, tmp_path)["confidence"] is None


def test_drift_decisions_insufficiency_and_shift():
    rng = np.random.default_rng(1)
    reference = rng.normal(size=(200, 6))
    assert drift_decision(reference, reference)["action"] == "retain"
    assert drift_decision(reference, reference + 10)["action"] == "rollback"
    assert drift_decision(reference, reference[:10])["action"] == "unavailable"


@pytest.mark.parametrize("kind", ["lstm", "gru", "transformer"])
def test_optional_sequence_architecture_has_actual_finite_forward_and_gradient(kind):
    torch = pytest.importorskip("torch")
    torch.manual_seed(1)
    model = sequence_model(6, kind)
    output = model(torch.randn(4, 12, 6))
    assert output.shape == (4,) and torch.isfinite(output).all()
    output.sum().backward()
    assert model.head.weight.grad is not None


def test_optional_sequence_absence_is_explicit(monkeypatch):
    import sys

    monkeypatch.setitem(sys.modules, "torch", None)
    result = validate_sequence([], [], [], [])
    assert result["status"] == "unavailable" and "PyTorch" in result["reason"]
