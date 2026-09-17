"""Finance primitives, checked against hand-computed values.

A business case is only as good as its arithmetic, and arithmetic is the part
nobody re-derives in the room. Every expected value here was worked out by hand
or from a closed-form identity, not captured from a previous run.
"""

from __future__ import annotations

import math

import pytest

from investment_case.finance import (
    CapitalStructure,
    cost_of_equity,
    discounted_payback_period,
    equivalent_annual_value,
    irr,
    npv,
    payback_period,
    profitability_index,
    wacc,
)


@pytest.fixture
def structure() -> CapitalStructure:
    return CapitalStructure(
        risk_free_rate=0.040,
        equity_risk_premium=0.055,
        beta=1.15,
        cost_of_debt=0.060,
        debt_weight=0.30,
        tax_rate=0.265,
    )


# --- cost of capital ----------------------------------------------------------


def test_capm_cost_of_equity(structure):
    # 4.0% + 1.15 * 5.5% = 10.325%
    assert cost_of_equity(structure) == pytest.approx(0.10325)


def test_wacc(structure):
    # 0.70 * 10.325% + 0.30 * 6.0% * (1 - 0.265) = 7.2275% + 1.3230% = 8.5505%
    assert wacc(structure) == pytest.approx(0.085505)


def test_debt_lowers_wacc_through_the_tax_shield(structure):
    """The whole reason capital structure appears in a platform business case."""
    unlevered = CapitalStructure(**{**structure.__dict__, "debt_weight": 0.0})
    assert wacc(structure) < wacc(unlevered)


def test_zero_tax_removes_the_shield_advantage(structure):
    """With no tax, debt only helps if it is cheaper than equity, not by shielding."""
    taxed = wacc(structure)
    untaxed = wacc(CapitalStructure(**{**structure.__dict__, "tax_rate": 0.0}))
    assert untaxed > taxed


def test_invalid_weights_are_rejected(structure):
    with pytest.raises(ValueError):
        CapitalStructure(**{**structure.__dict__, "debt_weight": 1.4})


# --- NPV ----------------------------------------------------------------------


def test_npv_of_a_known_series():
    # -1000 + 500/1.1 + 500/1.21 + 500/1.331
    # = -1000 + 454.5455 + 413.2231 + 375.6574 = 243.4260
    assert npv(0.10, [-1000, 500, 500, 500]) == pytest.approx(243.4260, abs=1e-3)


def test_npv_at_zero_rate_is_the_plain_sum():
    assert npv(0.0, [-1000, 400, 400, 400]) == pytest.approx(200.0)


def test_time_zero_flow_is_not_discounted():
    assert npv(0.25, [-100]) == pytest.approx(-100.0)


def test_higher_discount_rate_lowers_npv_of_a_conventional_project():
    flows = [-1000, 400, 400, 400]
    assert npv(0.15, flows) < npv(0.05, flows)


# --- IRR ----------------------------------------------------------------------


def test_irr_of_a_single_period_doubling():
    assert irr([-100, 110]) == pytest.approx(0.10, abs=1e-6)


def test_irr_makes_npv_zero():
    """The definition, asserted rather than assumed."""
    flows = [-1530, -800, -16, 934, 1360, 1430]
    rate = irr(flows)
    assert rate is not None
    assert npv(rate, flows) == pytest.approx(0.0, abs=1e-6)


def test_irr_is_none_when_nothing_is_invested():
    assert irr([100, 200, 300]) is None


def test_irr_is_none_when_nothing_is_returned():
    """A stream that never turns positive has no IRR. Reporting one would lie."""
    assert irr([-100, -50, -25]) is None


# --- payback ------------------------------------------------------------------


def test_payback_interpolates_within_the_year():
    # -100, then 50 and 50: cumulative reaches zero exactly at the end of year 2.
    assert payback_period([-100, 50, 50]) == pytest.approx(2.0)


def test_payback_partial_year():
    # After year 1 cumulative is -40; year 2 brings 80, so 40/80 = 0.5 of it.
    assert payback_period([-100, 60, 80]) == pytest.approx(1.5)


def test_payback_is_none_when_never_recovered():
    assert payback_period([-100, 10, 10]) is None


def test_discounted_payback_is_never_faster_than_simple():
    flows = [-100, 60, 80, 40]
    simple = payback_period(flows)
    discounted = discounted_payback_period(0.10, flows)
    assert discounted is not None and simple is not None
    assert discounted >= simple


# --- PI and EAV ---------------------------------------------------------------


def test_profitability_index_is_pv_of_inflows_over_outlay():
    flows = [-1000, 500, 500, 500]
    # PV of inflows = 1243.4260; PI = 1.2434
    assert profitability_index(0.10, flows) == pytest.approx(1.24343, abs=1e-4)


def test_pi_above_one_matches_positive_npv():
    flows = [-1000, 500, 500, 500]
    assert (profitability_index(0.10, flows) > 1) == (npv(0.10, flows) > 0)


def test_equivalent_annual_value_discounts_back_to_the_same_npv():
    """The identity that makes EAV safe to compare across different lives."""
    rate, flows = 0.10, [-1000, 500, 500, 500]
    eav = equivalent_annual_value(rate, flows)
    rebuilt = sum(eav / (1 + rate) ** t for t in range(1, len(flows)))
    assert rebuilt == pytest.approx(npv(rate, flows), abs=1e-6)


def test_eav_normalises_a_longer_horizon():
    """A 7-year project should not beat a 3-year one on duration alone."""
    short = [-500, 250, 250, 250]
    long = [-500, 140, 140, 140, 140, 140, 140, 140]
    assert npv(0.08, long) > npv(0.08, short)
    assert equivalent_annual_value(0.08, short) > equivalent_annual_value(0.08, long)


def test_eav_at_zero_rate_is_the_simple_average():
    assert equivalent_annual_value(0.0, [-300, 200, 200, 200]) == pytest.approx(100.0)


def test_eav_of_a_single_period_project_is_defined():
    assert not math.isnan(equivalent_annual_value(0.10, [-100, 120]))
