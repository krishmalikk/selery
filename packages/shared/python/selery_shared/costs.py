"""Pure analytical equity cost allowances, never a transaction simulator.

The model uses the same reference notional for both ends of a research horizon.
It allocates two commission/slippage/impact allowances, one full quoted-spread
assumption, one sale-side SEC/TAF allowance, and optional simple short borrow.
Regulatory amounts are unrounded analytical allowances, not broker invoices.
`as_of` means the regulatory charge date, not an inferred settlement date.

Official schedule sources, verified 2026-09-09:
https://www.sec.gov/newsroom/press-releases/2023-15
https://www.sec.gov/file/34-99973
https://www.sec.gov/files/rules/other/2025/34-102779.pdf
https://www.sec.gov/rules-regulations/fee-rate-advisories/2026-2
https://www.finra.org/rules-guidance/rule-filings/sr-finra-2024-019/fee-adjustment-schedule
https://www.finra.org/rules-guidance/rulebooks/corporate-organization/section-1-member-regulatory-fees
"""

from dataclasses import dataclass, fields, replace
from datetime import date
from decimal import Decimal, InvalidOperation, localcontext


MODEL_VERSION = "equity-costs-1.0.0"
VERIFIED_THROUGH = date(2026, 9, 9)
SUPPORTED_FROM = date(2024, 1, 1)
ZERO = Decimal("0")
SEC_SOURCES = (
    "https://www.sec.gov/file/34-99973",
    "https://www.sec.gov/files/rules/other/2025/34-102779.pdf",
    "https://www.sec.gov/rules-regulations/fee-rate-advisories/2026-2",
)
TAF_SOURCE = (
    "https://www.finra.org/rules-guidance/rule-filings/"
    "sr-finra-2024-019/fee-adjustment-schedule"
)


def _decimal(value: Decimal | float | int | str, name: str) -> Decimal:
    if isinstance(value, bool):
        raise ValueError(f"{name} must be a finite nonnegative number")
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise ValueError(f"{name} must be a finite nonnegative number") from None
    if not result.is_finite() or result < ZERO:
        raise ValueError(f"{name} must be a finite nonnegative number")
    return result


@dataclass(frozen=True)
class CostAssumptions:
    """Explicit USD/equity research assumptions; defaults are not observations.

    SPY spread defaults to an assumed $0.02 full spread. Slippage and impact
    are independent, user-supplied basis-point allowances per horizon endpoint.
    No liquidity, consolidated volume, or IEX market-share inference is made.
    Annual borrow is a decimal fraction (0.03 = 3%) on an ACT/365 basis.
    """

    commission_per_share: Decimal = Decimal("0")
    commission_minimum: Decimal = Decimal("0")
    full_spread: Decimal = Decimal("0.02")
    slippage_bps: Decimal = Decimal("1")
    market_impact_bps: Decimal = Decimal("0")
    annual_borrow_rate: Decimal = Decimal("0.03")
    spread_label: str = "Assumed SPY full spread; not an observed market spread"

    def __post_init__(self) -> None:
        for field in fields(self):
            if field.name != "spread_label":
                object.__setattr__(self, field.name, _decimal(getattr(self, field.name), field.name))
        if not isinstance(self.spread_label, str) or not self.spread_label.strip():
            raise ValueError("spread_label is required")


@dataclass(frozen=True)
class RegulatorySchedule:
    sec_effective_from: date
    sec_per_million: Decimal
    taf_effective_from: date
    taf_per_share: Decimal
    taf_cap: Decimal
    sec_source: str
    taf_source: str = TAF_SOURCE
    verified_through: date = VERIFIED_THROUGH


def regulatory_schedule(as_of: date) -> RegulatorySchedule:
    """Use a verified effective-dated schedule; never extrapolate unknown dates."""
    if type(as_of) is not date or not SUPPORTED_FROM <= as_of <= VERIFIED_THROUGH:
        raise ValueError("Regulatory rates are verified only for 2024-01-01 through 2026-09-09")
    if as_of >= date(2026, 4, 4):
        sec_date, sec_rate, source = date(2026, 4, 4), "20.60", SEC_SOURCES[2]
    elif as_of >= date(2025, 5, 14):
        sec_date, sec_rate, source = date(2025, 5, 14), "0", SEC_SOURCES[1]
    elif as_of >= date(2024, 5, 22):
        sec_date, sec_rate, source = date(2024, 5, 22), "27.80", SEC_SOURCES[0]
    else:
        # Coverage starts in 2024; this rate was already effective then.
        sec_date, sec_rate, source = date(2023, 2, 27), "8.00", "https://www.sec.gov/newsroom/press-releases/2023-15"
    if as_of >= date(2026, 1, 1):
        taf_date, taf_rate, taf_cap = date(2026, 1, 1), "0.000195", "9.79"
    else:
        taf_date, taf_rate, taf_cap = date(2024, 1, 1), "0.000166", "8.30"
    return RegulatorySchedule(sec_date, Decimal(sec_rate), taf_date, Decimal(taf_rate), Decimal(taf_cap), source)


@dataclass(frozen=True)
class CostBreakdown:
    commission: Decimal
    sec: Decimal
    taf: Decimal
    spread: Decimal
    slippage: Decimal
    borrow: Decimal
    market_impact: Decimal
    total: Decimal
    cost_bps: Decimal
    reference_notional: Decimal
    assumptions: CostAssumptions
    schedule: RegulatorySchedule
    as_of: date
    version: str = MODEL_VERSION
    methodology: str = "paired-horizon analytical allowance; one reference notional; no rounding"


def calculate_costs(
    price: float,
    shares: float,
    holding_days: float,
    assumptions: CostAssumptions,
    is_short: bool = False,
    as_of: date | None = None,
) -> CostBreakdown:
    """Estimate USD costs for one signal-event horizon, without any state.

    Pass the actual charge date for historical studies. An omitted date selects
    the pinned verification date, never the wall clock. Zero shares gives zero
    costs; price must be positive. Tiny prices below the TAF rate are exempt.
    """
    price_d = _decimal(price, "price")
    shares_d = _decimal(shares, "shares")
    days_d = _decimal(holding_days, "holding_days")
    if price_d == ZERO:
        raise ValueError("price must be positive")
    if not isinstance(assumptions, CostAssumptions):
        raise TypeError("assumptions must be CostAssumptions")
    if not isinstance(is_short, bool):
        raise ValueError("is_short must be boolean")
    effective_date = VERIFIED_THROUGH if as_of is None else as_of
    schedule = regulatory_schedule(effective_date)
    # Local context isolates calculation from callers' Decimal precision.
    with localcontext() as context:
        context.prec = 40
        notional = price_d * shares_d
        commission = 2 * max(shares_d * assumptions.commission_per_share, assumptions.commission_minimum) if shares_d else ZERO
        sec = notional * schedule.sec_per_million / Decimal("1000000")
        taf = min(shares_d * schedule.taf_per_share, schedule.taf_cap) if price_d >= schedule.taf_per_share else ZERO
        spread = shares_d * assumptions.full_spread
        slippage = 2 * notional * assumptions.slippage_bps / Decimal("10000")
        impact = 2 * notional * assumptions.market_impact_bps / Decimal("10000")
        borrow = notional * assumptions.annual_borrow_rate * days_d / Decimal("365") if is_short else ZERO
        total = commission + sec + taf + spread + slippage + borrow + impact
        bps = total / notional * Decimal("10000") if notional else ZERO
        return CostBreakdown(commission, sec, taf, spread, slippage, borrow, impact, total, bps, notional, assumptions, schedule, effective_date)


def spread_sensitivity(
    price: float,
    shares: float,
    holding_days: float,
    assumptions: CostAssumptions,
    is_short: bool = False,
    as_of: date | None = None,
) -> tuple[CostBreakdown, CostBreakdown, CostBreakdown]:
    """SPY full-spread assumption cases: $0.01, $0.02, $0.05."""
    return tuple(  # type: ignore[return-value]
        calculate_costs(price, shares, holding_days, replace(assumptions, full_spread=Decimal(value), spread_label=f"Assumed SPY full spread ${value}; not observed"), is_short, as_of)
        for value in ("0.01", "0.02", "0.05")
    )
