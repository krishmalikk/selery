"""SPY/ETF research context and pure calculations with explicit source dependencies."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import math
from urllib.parse import urlsplit

from selery_shared.costs import CostAssumptions, spread_sensitivity
from selery_shared.models import Feed

UTC = timezone.utc
SPY_PROSPECTUS = 'https://www.sec.gov/Archives/edgar/data/884394/000119312526022775/d77353d497.htm'
SPY_PRODUCT = 'https://www.ssga.com/us/en/intermediary/etfs/state-street-spdr-sp-500-etf-trust-spy'
OIC_VOLATILITY = 'https://www.optionseducation.org/news/understanding-the-rule-of-16-in-plain-terms'
VERIFIED_ON = '2026-09-09'
DEFINITIONS = {
    'name': 'State Street SPDR S&P 500 ETF Trust',
    'symbol': 'SPY',
    'structure': 'Unit investment trust',
    'benchmark': 'S&P 500 Index',
    'objective': 'Track the index price and income performance before fund expenses.',
    'expense_ratio_percent': 0.0945,
    'expense_ratio_status': 'Estimated annual ordinary operating expenses in the January 26, 2026 prospectus; not a live fee quote.',
    'prospectus_date': '2026-01-26',
    'source_url': SPY_PROSPECTUS,
    'verified_on': VERIFIED_ON,
    'version': 'spy-reference-2026-01',
}


@dataclass(frozen=True)
class Source:
    provider: str
    url: str
    observed_at: datetime
    available_at: datetime
    feed: str = 'delayed'
    synthetic: bool = False
    version: str = '1'

    def __post_init__(self):
        parsed = urlsplit(self.url)
        if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError('Research sources must have a public HTTPS citation')
        if self.observed_at.tzinfo is None or self.available_at.tzinfo is None:
            raise ValueError('Source timestamps must include timezone')
        if self.available_at < self.observed_at:
            raise ValueError('Availability cannot precede observation')
        if not self.provider or not self.version:
            raise ValueError('Source provider and version are required')

    def public(self):
        return {**asdict(self), 'observed_at': self.observed_at.isoformat(), 'available_at': self.available_at.isoformat()}


@dataclass(frozen=True)
class TimedValue:
    value: float
    source: Source
    unit: str
    currency: str = 'USD'

    def __post_init__(self):
        if isinstance(self.value, bool) or not math.isfinite(self.value):
            raise ValueError('Research input must be finite')


@dataclass(frozen=True)
class Constituent:
    symbol: str
    weight_percent: float
    sector: str = 'Unclassified'

    def __post_init__(self):
        if not self.symbol or not math.isfinite(self.weight_percent) or not 0 <= self.weight_percent <= 100:
            raise ValueError('Constituent requires a symbol and weight percent in [0, 100]')


def unavailable(reason: str, requires: list[str], *, sources=None):
    return {'status': 'unavailable', 'value': None, 'reason': reason, 'requires': requires, 'sources': sources or []}


def availability(source: Source, as_of: datetime, *, max_age: timedelta | None = None):
    if as_of.tzinfo is None:
        raise ValueError('As-of timestamp must include timezone')
    if source.synthetic:
        return 'Synthetic examples do not establish live research availability.'
    if source.available_at > as_of or source.observed_at > as_of:
        return 'Source was not available at the requested timestamp.'
    if max_age is not None and as_of - source.observed_at > max_age:
        return 'Source is older than this calculation permits.'
    return None


def nav_premium(price: TimedValue, nav: TimedValue, *, as_of: datetime):
    """A timestamp-aligned reference comparison, never a real-time fair-value claim."""
    for value in (price, nav):
        reason = availability(value.source, as_of)
        if reason:
            return unavailable(reason, ['aligned NAV and market reference'], sources=[price.source.public(), nav.source.public()])
    if price.value <= 0 or nav.value <= 0 or price.currency != nav.currency or price.unit != 'price' or nav.unit != 'nav':
        raise ValueError('Use positive market price and NAV in the same currency with explicit units')
    if abs((price.source.observed_at - nav.source.observed_at).total_seconds()) > 60:
        return unavailable('Market reference and NAV valuation timestamps differ by more than 60 seconds.',
                           ['market reference recorded at the NAV valuation timestamp'], sources=[price.source.public(), nav.source.public()])
    percent = (price.value / nav.value - 1) * 100
    return {'status': 'available', 'premium_percent': percent, 'label': 'Reference premium to NAV',
            'market_feed': price.source.feed, 'feed_label': 'IEX only' if price.source.feed == 'iex' else price.source.feed,
            'valuation_at': nav.source.observed_at.isoformat(), 'currency': nav.currency,
            'sources': [price.source.public(), nav.source.public()], 'method': '(reference price / NAV - 1) × 100',
            'limitation': 'An IEX reference is venue-limited. This is not an official consolidated premium/discount series.'}


def constituent_summary(holdings: list[Constituent], source: Source, *, as_of: datetime):
    reason = availability(source, as_of, max_age=timedelta(days=7))
    if reason:
        return unavailable(reason, ['current issuer constituent file'], sources=[source.public()])
    if not holdings:
        return unavailable('No constituent rows were supplied.', ['issuer constituent file'])
    if len({row.symbol for row in holdings}) != len(holdings):
        raise ValueError('Duplicate constituent symbols require reconciliation')
    weight = sum(row.weight_percent for row in holdings)
    if weight > 100.5:
        raise ValueError('Constituent weights exceed plausible 100% rounding tolerance')
    sectors = {}
    for row in holdings:
        sectors[row.sector] = sectors.get(row.sector, 0.0) + row.weight_percent
    ranked = sorted(holdings, key=lambda row: (-row.weight_percent, row.symbol))
    complete = 99.5 <= weight <= 100.5
    return {'status': 'available' if complete else 'partial', 'count': len(holdings), 'covered_weight_percent': weight,
            'uncovered_weight_percent': max(0, 100 - weight), 'top_ten': [asdict(row) for row in ranked[:10]],
            'top_ten_weight_percent': sum(row.weight_percent for row in ranked[:10]),
            'sector_weights_percent': sectors, 'sources': [source.public()],
            'limitation': 'Issuer constituent weights describe the fund, not any user account. Partial input is not renormalized.'}


def weighted_contributions(holdings: list[Constituent], returns_percent: dict[str, float]):
    """Arithmetic period contribution approximation; weights must precede the return period."""
    if len({row.symbol for row in holdings}) != len(holdings):
        raise ValueError('Duplicate constituent symbols require reconciliation')
    if sum(row.weight_percent for row in holdings) > 100.5:
        raise ValueError('Constituent weights exceed 100%')
    if any(isinstance(value, bool) or not math.isfinite(value) for value in returns_percent.values()):
        raise ValueError('Constituent returns must be finite percentages')
    rows = [{'symbol': row.symbol, 'weight_percent': row.weight_percent, 'return_percent': returns_percent.get(row.symbol),
             'contribution_percentage_points': None if row.symbol not in returns_percent else row.weight_percent * returns_percent[row.symbol] / 100}
            for row in holdings]
    covered = sum(row.weight_percent for row in holdings if row.symbol in returns_percent)
    return {'rows': rows, 'covered_weight_percent': covered,
            'known_contribution_percentage_points': sum(row['contribution_percentage_points'] or 0 for row in rows),
            'complete': covered >= 99.5,
            'limitation': 'Approximation uses supplied beginning-period weights and aligned returns; missing returns remain missing. No residual return is invented.'}


def iv_expected_move(spot: float, annualized_iv: float, horizon_days: float, *, day_count_basis=365):
    """Explicit square-root-of-time volatility proxy; annualized IV is a decimal fraction."""
    values = (spot, annualized_iv, horizon_days)
    if any(isinstance(value, bool) or not math.isfinite(value) or value <= 0 for value in values):
        raise ValueError('Spot, annualized IV fraction and horizon days must be finite and positive')
    if annualized_iv > 5 or horizon_days > 366 or day_count_basis not in (252, 365):
        raise ValueError('Check IV units, horizon (at most 366 days) and day-count basis (252 or 365)')
    move = spot * annualized_iv * math.sqrt(horizon_days / day_count_basis)
    return {'method': 'spot × annualized IV × sqrt(horizon / day-count basis)', 'move_usd': move,
            'move_percent': move / spot * 100, 'lower_reference': max(0, spot - move), 'upper_reference': spot + move,
            'horizon_days': horizon_days, 'day_count_basis': day_count_basis, 'annualized_iv_fraction': annualized_iv,
            'confidence': None, 'limitation': 'Volatility scaling proxy, not a forecast interval or a calibrated probability; jumps and volatility changes are not modeled.',
            'method_source': OIC_VOLATILITY}


def options_context(spot: TimedValue, annualized_iv: TimedValue, *, expiry: datetime, as_of: datetime):
    for value in (spot, annualized_iv):
        reason = availability(value.source, as_of, max_age=timedelta(minutes=15))
        if reason:
            return unavailable(reason, ['timestamped underlying and options IV'], sources=[spot.source.public(), annualized_iv.source.public()])
    if annualized_iv.source.feed != 'opra':
        return unavailable('Options IV provenance is not verified OPRA data.', ['OPRA-entitled timestamped options IV'])
    if abs((spot.source.observed_at - annualized_iv.source.observed_at).total_seconds()) > 60:
        return unavailable('Underlying and options observations are not aligned within 60 seconds.', ['aligned options and underlying snapshots'])
    if spot.unit != 'price' or annualized_iv.unit != 'annualized_iv_fraction' or expiry.tzinfo is None:
        raise ValueError('Options inputs need explicit price/IV units and timezone-aware expiry')
    if expiry <= as_of:
        return unavailable('Option expiry is not after the research timestamp.', ['unexpired options IV'])
    days = (expiry - as_of).total_seconds() / 86400
    result = iv_expected_move(spot.value, annualized_iv.value, days, day_count_basis=365)
    return {'status': 'available', **result, 'sources': [spot.source.public(), annualized_iv.source.public()],
            'underlying_feed': spot.source.feed, 'expiry': expiry.isoformat()}


def atm_straddle_proxy(*, spot: float, strike: float, call_bid: float, call_ask: float, put_bid: float, put_ask: float):
    """Pure paired-premium context from an explicitly selected common strike/expiry."""
    if any(isinstance(value, bool) or not math.isfinite(value) for value in (spot, strike, call_bid, call_ask, put_bid, put_ask)):
        raise ValueError('Option quote inputs must be finite')
    if spot <= 0 or strike <= 0 or min(call_bid, put_bid) < 0 or call_bid > call_ask or put_bid > put_ask:
        raise ValueError('Invalid underlying, strike, or crossed option quotes')
    if abs(strike / spot - 1) > .05:
        raise ValueError('Selected strike is more than 5% from the underlying reference')
    premium = (call_bid + call_ask + put_bid + put_ask) / 2
    return {'method': 'ATM call midpoint + same-expiry put midpoint', 'premium_proxy_usd': premium,
            'premium_proxy_percent': premium / spot * 100, 'strike': strike, 'confidence': None,
            'limitation': 'A midpoint premium proxy is not a probable move, realized price, or assured attainable value. Supply matched strike, expiry and timestamps.'}


def cost_context(*, price: float | None = None, units: float | None = None, horizon_days: float = 1,
                 charge_date: date = date(2026, 9, 9)):
    result = {'fund_expense_ratio_percent': DEFINITIONS['expense_ratio_percent'],
              'fund_expense_source': SPY_PROSPECTUS, 'fund_expense_as_of': DEFINITIONS['prospectus_date'],
              'assumed_full_spread_usd': [.01, .02, .05],
              'spread_label': 'Explicit SPY full-spread assumptions; not observed market spreads',
              'fee_note': 'Fund operating expenses are embedded in NAV; avoid subtracting them twice from observed ETF return data.',
              'liquidity_note': 'IEX volume does not establish consolidated liquidity or market impact.'}
    if price is None or units is None:
        result['analytical_cases'] = unavailable('Supply reference price and research units for cost sensitivity.', ['price', 'units'])
    else:
        cases = spread_sensitivity(price, units, horizon_days, CostAssumptions(), as_of=charge_date)
        result['analytical_cases'] = [{'assumed_full_spread_usd': float(case.assumptions.full_spread),
                                      'total_usd': float(case.total), 'cost_bps': float(case.cost_bps),
                                      'version': case.version, 'as_of': case.as_of.isoformat()} for case in cases]
    return result


def spy_snapshot(*, as_of: datetime | None = None, feed: Feed = Feed.IEX, price: TimedValue | None = None,
                 nav: TimedValue | None = None, holdings: list[Constituent] | None = None,
                 holdings_source: Source | None = None, annualized_iv: TimedValue | None = None,
                 expiry: datetime | None = None, macro: dict[str, TimedValue] | None = None):
    """Default metadata endpoint has useful definitions and honest missing-data states."""
    as_of = as_of or datetime.now(UTC)
    if as_of.tzinfo is None:
        raise ValueError('As-of timestamp must include timezone')
    macro_results = {}
    for series, value in (macro or {}).items():
        reason = availability(value.source, as_of)
        macro_results[series] = unavailable(reason, ['point-in-time macro release']) if reason else {
            'status': 'available', 'value': value.value, 'unit': value.unit, 'sources': [value.source.public()]}
    return {'symbol': 'SPY', 'as_of': as_of.isoformat(), 'version': 'spy-domain-1', 'definitions': dict(DEFINITIONS),
            'feed': str(feed), 'feed_label': 'IEX only' if feed == Feed.IEX else str(feed),
            'holdings': constituent_summary(holdings, holdings_source, as_of=as_of) if holdings is not None and holdings_source else
                        unavailable('Issuer constituent snapshot has not been supplied.', ['dated issuer holdings file'], sources=[SPY_PRODUCT]),
            'nav_premium': nav_premium(price, nav, as_of=as_of) if price and nav else
                        unavailable('Timestamp-aligned NAV and market references have not been supplied.', ['issuer NAV', 'same-time market reference']),
            'options': options_context(price, annualized_iv, expiry=expiry, as_of=as_of) if price and annualized_iv and expiry else
                        unavailable('Options research data and entitlement have not been configured.', ['OPRA entitlement', 'timestamped IV', 'expiry', 'underlying reference']),
            'macro': macro_results or unavailable('Point-in-time macro observations have not been supplied.', ['FRED API key', 'historical release vintage']),
            'cost_context': cost_context(), 'data_dependencies': {
                'volume_features': 'needs SIP data' if feed != Feed.SIP else 'Available only on verified consolidated bars',
                'options': 'OPRA entitlement is separate from equity SIP',
                'holdings_history': 'Current constituent weights must not be reused as historical beginning-period weights',
                'contribution': 'Requires aligned constituent returns and weights known at the period start'}}
