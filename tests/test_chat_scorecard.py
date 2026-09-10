import importlib.util
from pathlib import Path
import pytest

spec=importlib.util.spec_from_file_location('chat_scorecard',Path(__file__).parents[1]/'scripts/evaluate_chat_answers.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)

def test_unknown_citation_and_unmeasured_quality_do_not_pass():
    result=module.score({'case':'stale_next_session','answer':'Observation [known]. Unsupported [invented].','supplied_source_ids':['known']})
    assert result['unknown_source_ids']==['invented'] and result['recognized_citation_fraction']==.5
    assert result['verdict']=='pending_manual_review' and result['metrics']['cost_usd'] is None

def test_manual_failure_and_invalid_metrics_never_pass():
    record={'case':'conflicting_news','answer':'Source [known].','supplied_source_ids':['known'],'review':{key:True for key in module.REVIEW_FIELDS},'cost_usd':.002,'latency_ms':100}
    assert module.score(record)['verdict']=='pass'
    record['review']['factual_support']=False
    assert module.score(record)['verdict']=='fail'
    record['cost_usd']=-1
    with pytest.raises(ValueError):module.score(record)
