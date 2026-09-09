from datetime import datetime, timedelta, timezone
import math
import pytest

from selery_api.domain import (Source, TimedValue, Constituent, atm_straddle_proxy, constituent_summary, cost_context,
                              iv_expected_move, nav_premium, options_context, spy_snapshot, weighted_contributions)
from selery_shared.models import Feed

NOW = datetime(2026, 9, 9, 20, tzinfo=timezone.utc)


def source(*, feed='iex', offset=0, synthetic=False):
    return Source('fixture-input', 'https://example.com/data', NOW + timedelta(seconds=offset),
                  NOW + timedelta(seconds=offset), feed=feed, synthetic=synthetic)


def test_default_domain_never_fabricates_live_data():
    snapshot = spy_snapshot(as_of=NOW)
    assert snapshot['definitions']['expense_ratio_percent'] == .0945
    assert snapshot['definitions']['prospectus_date'] == '2026-01-26'
    assert snapshot['feed_label'] == 'IEX only'
    for feature in ('holdings', 'nav_premium', 'options', 'macro'):
        assert snapshot[feature]['status'] == 'unavailable'
    assert snapshot['data_dependencies']['volume_features'] == 'needs SIP data'


def test_nav_premium_requires_aligned_sources_and_preserves_venue_label():
    price, nav = TimedValue(101, source(), 'price'), TimedValue(100, source(feed='issuer'), 'nav')
    result = nav_premium(price, nav, as_of=NOW)
    assert result['premium_percent'] == pytest.approx(1)
    assert result['feed_label'] == 'IEX only'
    old_nav = TimedValue(100, source(offset=-3600, feed='issuer'), 'nav')
    assert nav_premium(price, old_nav, as_of=NOW)['status'] == 'unavailable'
    future_price = TimedValue(101, source(offset=60), 'price')
    assert nav_premium(future_price, nav, as_of=NOW)['status'] == 'unavailable'


def test_partial_holdings_not_renormalized_and_future_weights_rejected():
    holdings = [Constituent('AAA', 20, 'Technology'), Constituent('BBB', 30, 'Technology'), Constituent('CCC', 10, 'Health')]
    summary = constituent_summary(holdings, source(feed='issuer'), as_of=NOW)
    assert summary['status'] == 'partial'
    assert summary['covered_weight_percent'] == 60 and summary['sector_weights_percent']['Technology'] == 50
    assert summary['top_ten'][0]['symbol'] == 'BBB'
    assert constituent_summary(holdings, source(offset=60), as_of=NOW)['status'] == 'unavailable'
    with pytest.raises(ValueError, match='Duplicate'):
        constituent_summary([holdings[0], holdings[0]], source(), as_of=NOW)


def test_contributions_keep_missing_returns_and_correct_percent_units():
    values = weighted_contributions([Constituent('AAA', 60), Constituent('BBB', 40)], {'AAA': 2})
    assert values['known_contribution_percentage_points'] == pytest.approx(1.2)
    assert values['rows'][1]['contribution_percentage_points'] is None
    assert values['covered_weight_percent'] == 60 and not values['complete']


def test_iv_proxy_units_day_count_and_missing_confidence():
    result = iv_expected_move(100, .2, 365)
    assert result['move_usd'] == 20 and result['move_percent'] == 20
    assert result['confidence'] is None
    assert iv_expected_move(100, .2, 1, day_count_basis=252)['move_usd'] == pytest.approx(20 / math.sqrt(252))
    with pytest.raises(ValueError, match='IV units'):
        iv_expected_move(100, 20, 30)


def test_options_need_opra_freshness_alignment_and_valid_expiry():
    spot = TimedValue(100, source(), 'price')
    iv = TimedValue(.2, source(feed='opra'), 'annualized_iv_fraction')
    expiry = NOW + timedelta(days=30)
    result = options_context(spot, iv, expiry=expiry, as_of=NOW)
    assert result['status'] == 'available' and result['underlying_feed'] == 'iex'
    assert options_context(spot, TimedValue(.2, source(), 'annualized_iv_fraction'), expiry=expiry, as_of=NOW)['status'] == 'unavailable'
    assert options_context(spot, iv, expiry=NOW, as_of=NOW)['status'] == 'unavailable'
    assert options_context(spot, iv, expiry=expiry, as_of=NOW+timedelta(hours=1))['status'] == 'unavailable'


def test_synthetic_inputs_cannot_establish_live_domain_availability():
    values = [Constituent('AAA', 100)]
    assert constituent_summary(values, source(synthetic=True), as_of=NOW)['status'] == 'unavailable'
    with pytest.raises(ValueError):
        Source('x', 'https://example.com', NOW, NOW-timedelta(seconds=1))


def test_straddle_context_is_price_proxy_and_crossed_quotes_rejected():
    result = atm_straddle_proxy(spot=100, strike=100, call_bid=2, call_ask=3, put_bid=1, put_ask=2)
    assert result['premium_proxy_usd'] == 4 and result['confidence'] is None
    with pytest.raises(ValueError, match='crossed'):
        atm_straddle_proxy(spot=100, strike=100, call_bid=3, call_ask=2, put_bid=1, put_ask=2)


def test_cost_context_delegates_to_canonical_cost_model():
    context = cost_context(price=100, units=10)
    assert [case['assumed_full_spread_usd'] for case in context['analytical_cases']] == [.01, .02, .05]
    assert context['analytical_cases'][0]['total_usd'] < context['analytical_cases'][2]['total_usd']
    assert 'embedded in NAV' in context['fee_note']
    assert spy_snapshot(as_of=NOW, feed=Feed.SIP)['data_dependencies']['volume_features'] != 'needs SIP data'
