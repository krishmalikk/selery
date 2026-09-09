import numpy as np
import pytest
from selery_api.ml import FEATURE_NAMES, qualify_sequence
from selery_api.storage import Store

SCOPE = {
    "symbol": "SPY",
    "feed": "iex",
    "timeframe": "5m",
    "strategy": "ema_cross",
    "strategy_version": "1",
    "horizon_bars": 2,
}


def dataset():
    rng = np.random.default_rng(3)
    y = np.tile([0, 1], 160)
    x = rng.normal(0, 0.2, size=(320, 4, len(FEATURE_NAMES))).astype(np.float32)
    # The earlier sequence contains information absent from the latest-row baseline.
    x[:, 0, 0] = (2 * y - 1) * 2
    starts = 1_600_000_000 + np.arange(320) * 172800
    available = starts[:, None] - np.array([900, 600, 300, 0])[None, :]
    return x, y, starts, starts + 300, available


def tiny_model(features, kind):
    import torch

    class TinySequence(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.head = torch.nn.Linear(features, 1)
            torch.nn.init.zeros_(self.head.weight)
            torch.nn.init.zeros_(self.head.bias)

        def forward(self, values):
            return self.head(values[:, 0]).squeeze(-1)

    return TinySequence()


@pytest.fixture
def store():
    result = Store("sqlite:///:memory:")
    yield result
    result.engine.dispose()


def qualify(store, values=None, **kwargs):
    x, y, starts, ends, available = values or dataset()
    return qualify_sequence(
        x,
        y,
        starts,
        ends,
        store=store,
        scope=SCOPE,
        available_at=available,
        epochs=15,
        model_factory=tiny_model,
        **kwargs,
    )


def test_real_sequence_training_calibration_and_final_holdout_qualification(store):
    pytest.importorskip("torch")
    report, artifact = qualify(store)
    assert report["status"] == "validated"
    assert report["calibrated"] and report["validated"]
    assert report["holdout_brier"] < report["baseline_holdout_brier"]
    assert report["holdout_events"] == 64
    assert len(report["folds"]) == 3
    assert all(fold["latest_training_label"] < fold["validation_start"] - 86400 for fold in report["folds"])
    assert report["oof_calibration_events"] > 100
    assert report["reliability"] and report["baseline_reliability"]
    assert artifact["state_dict"] and artifact["scope"] == SCOPE
    assert store.list("models") == []  # Qualification itself never promotes or serializes a model.


def test_final_holdout_cannot_influence_weights_scaler_or_calibrators(store):
    torch = pytest.importorskip("torch")
    first, artifact = qualify(store)
    x, y, starts, ends, available = dataset()
    y[-64:] = 1 - y[-64:]
    x[-64:] *= 10
    second_store = Store("sqlite:///:memory:")
    try:
        second, altered = qualify(second_store, (x, y, starts, ends, available))
        for key in artifact["state_dict"]:
            assert torch.equal(artifact["state_dict"][key], altered["state_dict"][key])
        assert np.array_equal(artifact["scaler"].mean_, altered["scaler"].mean_)
        assert np.array_equal(artifact["calibrator"].coef_, altered["calibrator"].coef_)
        assert np.array_equal(artifact["baseline_calibrator"].coef_, altered["baseline_calibrator"].coef_)
        assert first["holdout_brier"] != second["holdout_brier"]
        assert second["status"] == "rejected"
    finally:
        second_store.engine.dispose()


def test_sequence_holdout_claim_prevents_architecture_search_on_same_labels(store):
    pytest.importorskip("torch")
    qualify(store)
    blocked, artifact = qualify(store, kind="gru")
    assert blocked["status"] == "unavailable" and "overlaps" in blocked["reason"] and artifact is None


def test_future_sequence_steps_and_invalid_intervals_rejected_before_fitting(store):
    pytest.importorskip("torch")
    x, y, starts, ends, available = dataset()
    available[0, -1] = starts[0] + 1
    report, artifact = qualify(store, (x, y, starts, ends, available))
    assert report["status"] == "unavailable" and artifact is None
    assert store.list("settings") == []
    x, y, starts, ends, available = dataset()
    ends[0] = starts[0] - 1
    assert qualify(store, (x, y, starts, ends, available))[0]["status"] == "unavailable"


def test_sequence_training_restores_global_rng_state(store):
    torch = pytest.importorskip("torch")
    torch.manual_seed(97)
    before = torch.random.get_rng_state().clone()
    qualify(store)
    assert torch.equal(before, torch.random.get_rng_state())


def test_optional_sequence_qualification_dependency_absence(monkeypatch, store):
    import sys

    monkeypatch.setitem(sys.modules, "torch", None)
    report, artifact = qualify(store)
    assert report["status"] == "unavailable" and "PyTorch" in report["reason"] and artifact is None


def test_transformer_after_numba_indicators_uses_safe_cpu_thread_budget():
    torch = pytest.importorskip("torch")
    from selery_api.ml import sequence_model
    from selery_shared.indicators import chart_indicators
    from selery_shared.models import Bar, Feed

    bars = [
        Bar(
            symbol="SPY",
            time=1_600_000_000 + index * 300,
            available_at=1_600_000_300 + index * 300,
            open=100 + index * 0.1,
            close=100 + index * 0.1,
            high=101 + index * 0.1,
            low=99 + index * 0.1,
            feed=Feed.IEX,
        )
        for index in range(100)
    ]
    chart_indicators(bars, Feed.IEX)
    model = sequence_model(len(FEATURE_NAMES), "transformer")
    assert torch.get_num_threads() == 1
    output = model(torch.randn(4, 12, len(FEATURE_NAMES)))
    output.sum().backward()
    assert torch.isfinite(output).all() and torch.isfinite(model.head.weight.grad).all()
