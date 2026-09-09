import numpy as np
import pytest
from selery_api.ml import fractional_difference,purged_walk_forward,drift_score,train_meta
from selery_api.storage import Store

def test_fractional_difference_is_prefix_invariant():
    prefix=np.arange(1,60,dtype=float)
    full=np.concatenate([prefix,[10000,-10000]])
    assert np.allclose(fractional_difference(prefix),fractional_difference(full)[:len(prefix)],equal_nan=True)

def test_purge_removes_overlapping_label_windows():
    starts=np.arange(30)*100;ends=starts+250
    for train,valid in purged_walk_forward(starts,ends,3,100):
        assert np.all(ends[train]<starts[valid[0]]-100)
        assert not set(train)&set(valid)

def test_invalid_interval_rejected():
    with pytest.raises(ValueError):list(purged_walk_forward([1,2],[0,3]))

def test_no_fabricated_model_on_missing_labels():
    result=train_meta([],[],Store('sqlite:///:memory:'),'/tmp/selery-empty-model-test')
    assert result['status']=='unavailable' and 'No model was trained' in result['reason']

def test_drift_reference_bins():
    reference=np.arange(100)
    assert drift_score(reference,reference)==pytest.approx(0)
    assert drift_score(reference,reference+200)>1
