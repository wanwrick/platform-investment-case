"""Discount rate and valuation primitives.

Plain implementations so every number in the memo can be traced to a formula
rather than to a library default. Framework sources are named in the README.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


# --- Cost of capital (CAPM, then WACC) ---------------------------------------


@dataclass(frozen=True)
class CapitalStructure:
    """Inputs to the discount rate.

    Rates are decimals: 0.04 is 4%.
    """

    risk_free_rate: float
    equity_risk_premium: float
    beta: float
    cost_of_debt: float
    debt_weight: float
    tax_rate: float

    def __post_init__(self) -> None:
        if not 0.0 <= self.debt_weight < 1.0:
            raise ValueError("debt_weight must be in [0, 1)")
        if not 0.0 <= self.tax_rate < 1.0:
            raise ValueError("tax_rate must be in [0, 1)")

    @property
    def equity_weight(self) -> float:
        return 1.0 - self.debt_weight


def cost_of_equity(structure: CapitalStructure) -> float:
    """CAPM: Re = Rf + beta * ERP."""
    return structure.risk_free_rate + structure.beta * structure.equity_risk_premium


def wacc(structure: CapitalStructure) -> float:
    """WACC = We*Re + Wd*Rd*(1-t).

    The tax shield applies to debt only, which is why a levered firm discounts
    the same project at a lower rate than an unlevered one.
    """
    return (
        structure.equity_weight * cost_of_equity(structure)
        + structure.debt_weight * structure.cost_of_debt * (1.0 - structure.tax_rate)
    )


# --- Valuation ----------------------------------------------------------------


def npv(rate: float, cash_flows: list[float]) -> float:
    """Net present value. `cash_flows[0]` is t=0 and is not discounted."""
    if rate <= -1.0:
        raise ValueError("rate must be greater than -1")
    return sum(cf / (1.0 + rate) ** t for t, cf in enumerate(cash_flows))


def irr(cash_flows: list[float], *, tolerance: float = 1e-9, max_iterations: int = 200) -> float | None:
    """Internal rate of return by bisection.

    Returns None when no sign change exists in the series, which is the honest
    answer: a stream that never turns positive has no IRR, and reporting one
    would be worse than reporting nothing.
    """
    if not cash_flows or all(cf >= 0 for cf in cash_flows) or all(cf <= 0 for cf in cash_flows):
        return None

    low, high = -0.9999, 10.0
    npv_low, npv_high = npv(low, cash_flows), npv(high, cash_flows)
    if npv_low * npv_high > 0:
        return None

    for _ in range(max_iterations):
        mid = (low + high) / 2.0
        value = npv(mid, cash_flows)
        if abs(value) < tolerance:
            return mid
        if value * npv_low < 0:
            high = mid
        else:
            low, npv_low = mid, value
    return (low + high) / 2.0


def payback_period(cash_flows: list[float]) -> float | None:
    """Years until cumulative cash flow turns positive, interpolated."""
    cumulative = 0.0
    for year, flow in enumerate(cash_flows):
        previous = cumulative
        cumulative += flow
        if cumulative >= 0 and year > 0:
            if flow == 0:
                return float(year)
            return (year - 1) + (-previous / flow)
    return None


def discounted_payback_period(rate: float, cash_flows: list[float]) -> float | None:
    """Payback on discounted flows. Always at least as long as simple payback."""
    discounted = [cf / (1.0 + rate) ** t for t, cf in enumerate(cash_flows)]
    return payback_period(discounted)


def profitability_index(rate: float, cash_flows: list[float]) -> float | None:
    """PV of inflows divided by the initial outlay.

    The tie-breaker when two options both clear the hurdle but one costs far
    more. NPV ranks by size; PI ranks by return per dollar committed.
    """
    outlay = -cash_flows[0]
    if outlay <= 0:
        return None
    return npv(rate, [0.0, *cash_flows[1:]]) / outlay


def equivalent_annual_value(rate: float, cash_flows: list[float]) -> float:
    """NPV restated as a level annual amount over the same horizon.

    Needed whenever options have different useful lives, because comparing a
    3-year NPV to a 7-year NPV rewards the longer one for nothing but duration.
    """
    years = len(cash_flows) - 1
    if years <= 0:
        return 0.0
    if math.isclose(rate, 0.0):
        return npv(rate, cash_flows) / years
    annuity_factor = (1.0 - (1.0 + rate) ** -years) / rate
    return npv(rate, cash_flows) / annuity_factor
