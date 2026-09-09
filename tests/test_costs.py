"""Hand-computed tests for pure research costs. No network or wall clock."""

from dataclasses import FrozenInstanceError
from datetime import date
from decimal import Decimal, localcontext
import unittest

from selery_shared.costs import CostAssumptions, calculate_costs, regulatory_schedule, spread_sensitivity


class CostTests(unittest.TestCase):
    def test_hand_computed_reference_case(self):
        # $50,000 notional: SEC 1.03 + TAF .0195 + spread 2 + slippage 10.
        value = calculate_costs(500, 100, 2, CostAssumptions(), as_of=date(2026, 9, 9))
        self.assertEqual(value.sec, Decimal("1.03"))
        self.assertEqual(value.taf, Decimal("0.0195"))
        self.assertEqual(value.spread, Decimal("2"))
        self.assertEqual(value.slippage, Decimal("10"))
        self.assertEqual(value.total, Decimal("13.0495"))
        self.assertEqual(value.cost_bps, Decimal("2.6099"))

    def test_commission_minimum_and_short_borrow(self):
        assumptions = CostAssumptions(commission_per_share="0.005", commission_minimum="1", slippage_bps="0", market_impact_bps="2", annual_borrow_rate="0.0365")
        value = calculate_costs(100, 100, 10, assumptions, True, date(2026, 9, 9))
        self.assertEqual(value.commission, Decimal("2"))
        self.assertEqual(value.borrow, Decimal("10"))
        self.assertEqual(value.market_impact, Decimal("4"))
        self.assertEqual(value.total, Decimal("18.2255"))
        self.assertEqual(calculate_costs(100, 100, 10, assumptions).borrow, 0)

    def test_commission_per_share_above_minimum(self):
        value = calculate_costs(100, 1000, 0, CostAssumptions(commission_per_share="0.005", commission_minimum="1"))
        self.assertEqual(value.commission, Decimal("10"))

    def test_regulatory_change_boundaries(self):
        for day, sec, taf in (
            (date(2024, 5, 21), "8", "0.000166"),
            (date(2024, 5, 22), "27.80", "0.000166"),
            (date(2025, 5, 13), "27.80", "0.000166"),
            (date(2025, 5, 14), "0", "0.000166"),
            (date(2025, 12, 31), "0", "0.000166"),
            (date(2026, 1, 1), "0", "0.000195"),
            (date(2026, 4, 3), "0", "0.000195"),
            (date(2026, 4, 4), "20.60", "0.000195"),
        ):
            with self.subTest(day=day):
                schedule = regulatory_schedule(day)
                self.assertEqual(schedule.sec_per_million, Decimal(sec))
                self.assertEqual(schedule.taf_per_share, Decimal(taf))

    def test_taf_caps_and_low_price_exemption(self):
        self.assertEqual(calculate_costs(100, 100000, 1, CostAssumptions()).taf, Decimal("9.79"))
        self.assertEqual(calculate_costs(100, 100000, 1, CostAssumptions(), as_of=date(2024, 1, 1)).taf, Decimal("8.30"))
        self.assertEqual(calculate_costs(0.0001, 100, 1, CostAssumptions()).taf, 0)

    def test_zero_shares_never_charge_minimum(self):
        value = calculate_costs(500, 0, 5, CostAssumptions(commission_minimum="5"), True)
        self.assertEqual(value.total, 0)
        self.assertEqual(value.cost_bps, 0)

    def test_sensitivity_is_exact_and_does_not_mutate(self):
        assumptions = CostAssumptions()
        low, base, high = spread_sensitivity(500, 100, 1, assumptions)
        self.assertEqual(base.total - low.total, Decimal("1"))
        self.assertEqual(high.total - base.total, Decimal("3"))
        self.assertEqual(assumptions.full_spread, Decimal("0.02"))
        with self.assertRaises(FrozenInstanceError):
            assumptions.full_spread = Decimal("1")

    def test_dates_outside_verified_coverage_fail(self):
        for day in (date(2023, 12, 31), date(2026, 9, 10)):
            with self.assertRaises(ValueError):
                calculate_costs(500, 100, 1, CostAssumptions(), as_of=day)

    def test_invalid_numbers_fail(self):
        for invalid in (-1, float("inf"), float("nan"), True, "garbage"):
            for index in range(3):
                args = [100, 100, 1]
                args[index] = invalid
                with self.subTest(invalid=invalid, index=index), self.assertRaises(ValueError):
                    calculate_costs(*args, CostAssumptions())
            with self.assertRaises(ValueError):
                CostAssumptions(full_spread=invalid)
        with self.assertRaises(ValueError):
            calculate_costs(0, 100, 1, CostAssumptions())

    def test_decimal_context_does_not_change_result(self):
        expected = calculate_costs(500, 100, 7, CostAssumptions(), True)
        with localcontext() as context:
            context.prec = 6
            actual = calculate_costs(500, 100, 7, CostAssumptions(), True)
        self.assertEqual(expected, actual)


if __name__ == "__main__":
    unittest.main()
