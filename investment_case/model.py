"""The cash flow model: how a platform option turns into a stream of dollars.

The structure that matters is this. Costs are largely committed up front and
are reasonably knowable. Benefits are not: almost all of them depend on how
many teams actually move onto the platform, and adoption is the one input
nobody can promise. So adoption is modeled explicitly as an S-curve with a
ceiling, and every sensitivity in this repo moves it.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Iterable

from .finance import (
    CapitalStructure,
    discounted_payback_period,
    equivalent_annual_value,
    irr,
    npv,
    payback_period,
    profitability_index,
    wacc,
)


@dataclass(frozen=True)
class AdoptionCurve:
    """Share of eligible teams on the platform, by year.

    A logistic curve, because platform adoption is not linear. It is slow while
    the first team proves it works, fast once there is a reference
    implementation, then flat against a ceiling that is set by how many teams
    could realistically ever move.
    """

    ceiling: float           # maximum share of teams that will ever migrate
    midpoint_year: float     # year at which half the ceiling is reached
    steepness: float         # how sharply the curve turns

    def share(self, year: int) -> float:
        if year <= 0:
            return 0.0
        return self.ceiling / (1.0 + math.exp(-self.steepness * (year - self.midpoint_year)))


@dataclass(frozen=True)
class BenefitDrivers:
    """What the platform is worth per year at full adoption, before ramp."""

    engineering_hours_saved: float
    fully_loaded_hourly_rate: float
    licences_decommissioned: float
    licence_unit_cost: float
    incidents_avoided: float
    incident_cost: float
    analyst_hours_saved: float
    analyst_hourly_rate: float
    legacy_run_cost_avoided: float = 0.0

    @property
    def annual_value_at_full_adoption(self) -> float:
        """Value against the do-nothing baseline, not in absolute terms.

        `legacy_run_cost_avoided` is the largest line for any option that
        retires the existing warehouse, and leaving it out is the most common
        way a platform business case understates itself. It is not free money:
        it only lands once teams have actually moved, which is why it ramps
        with adoption like every other benefit here.
        """
        return (
            self.engineering_hours_saved * self.fully_loaded_hourly_rate
            + self.licences_decommissioned * self.licence_unit_cost
            + self.incidents_avoided * self.incident_cost
            + self.analyst_hours_saved * self.analyst_hourly_rate
            + self.legacy_run_cost_avoided
        )


@dataclass(frozen=True)
class CostProfile:
    """What the option costs. Upfront is t=0; the rest recur."""

    upfront_capex: float
    upfront_opex: float
    annual_platform_cost: float
    annual_platform_cost_growth: float
    annual_run_team_cost: float
    migration_cost_per_year: list[float] = field(default_factory=list)

    def year_cost(self, year: int) -> float:
        if year == 0:
            return self.upfront_capex + self.upfront_opex
        platform = self.annual_platform_cost * (1.0 + self.annual_platform_cost_growth) ** (year - 1)
        migration = (
            self.migration_cost_per_year[year - 1]
            if year - 1 < len(self.migration_cost_per_year)
            else 0.0
        )
        return platform + self.annual_run_team_cost + migration


@dataclass(frozen=True)
class Option:
    """One path the organization could take."""

    key: str
    name: str
    thesis: str
    costs: CostProfile
    benefits: BenefitDrivers
    adoption: AdoptionCurve
    capability_ceiling: float   # 0 to 1: the most of the estate it can ever serve
    switching_cost: float       # cost to leave this option later
    lock_in_note: str = ""


@dataclass(frozen=True)
class Assumptions:
    horizon_years: int
    capital_structure: CapitalStructure
    depreciation_years: int

    def __post_init__(self) -> None:
        # Depreciation past the horizon is never booked, which silently drops
        # part of the tax shield from every option. Refuse rather than mis-state.
        if self.depreciation_years > self.horizon_years:
            raise ValueError(
                f"depreciation_years ({self.depreciation_years}) exceeds "
                f"horizon_years ({self.horizon_years}); the tail would never be expensed"
            )

    @property
    def discount_rate(self) -> float:
        return wacc(self.capital_structure)


@dataclass
class YearRow:
    year: int
    adoption: float
    gross_benefit: float
    cost: float
    depreciation: float
    ebit: float
    tax: float
    nopat: float
    free_cash_flow: float


@dataclass
class OptionResult:
    option: Option
    rows: list[YearRow]
    discount_rate: float

    @property
    def cash_flows(self) -> list[float]:
        return [row.free_cash_flow for row in self.rows]

    @property
    def npv(self) -> float:
        return npv(self.discount_rate, self.cash_flows)

    @property
    def irr(self) -> float | None:
        return irr(self.cash_flows)

    @property
    def payback(self) -> float | None:
        return payback_period(self.cash_flows)

    @property
    def discounted_payback(self) -> float | None:
        return discounted_payback_period(self.discount_rate, self.cash_flows)

    @property
    def profitability_index(self) -> float | None:
        return profitability_index(self.discount_rate, self.cash_flows)

    @property
    def equivalent_annual_value(self) -> float:
        return equivalent_annual_value(self.discount_rate, self.cash_flows)

    @property
    def total_investment(self) -> float:
        return -self.cash_flows[0]

    @property
    def peak_adoption(self) -> float:
        return max(row.adoption for row in self.rows)


def build_schedule(option: Option, assumptions: Assumptions) -> OptionResult:
    """Turn an option into a year-by-year free cash flow schedule.

    Free cash flow here is NOPAT plus depreciation less capex. Depreciation is
    not a cash cost but it shields tax, so removing it from the tax base and
    adding it back is what separates this from a spreadsheet that discounts
    accounting profit.
    """
    tax_rate = assumptions.capital_structure.tax_rate
    capex = option.costs.upfront_capex
    annual_depreciation = (
        capex / assumptions.depreciation_years if assumptions.depreciation_years else 0.0
    )
    full_value = option.benefits.annual_value_at_full_adoption

    rows: list[YearRow] = []
    for year in range(assumptions.horizon_years + 1):
        # Capability is a ceiling on adoption, not a discount on it. A team
        # whose workload the platform cannot serve does not migrate at reduced
        # value; it does not migrate. Multiplying the two instead would penalise
        # every option twice for the same constraint.
        adoption = min(option.adoption.share(year), option.capability_ceiling)
        gross_benefit = full_value * adoption
        cost = option.costs.year_cost(year)
        depreciation = annual_depreciation if 1 <= year <= assumptions.depreciation_years else 0.0

        if year == 0:
            # t=0 is the outlay. Nothing is operating yet, so no tax effect.
            rows.append(
                YearRow(
                    year=0,
                    adoption=0.0,
                    gross_benefit=0.0,
                    cost=cost,
                    depreciation=0.0,
                    ebit=0.0,
                    tax=0.0,
                    nopat=0.0,
                    free_cash_flow=-cost,
                )
            )
            continue

        ebit = gross_benefit - cost - depreciation
        # A loss shields tax elsewhere in a profitable firm, so the benefit is
        # symmetric rather than floored at zero.
        tax = ebit * tax_rate
        nopat = ebit - tax
        free_cash_flow = nopat + depreciation

        rows.append(
            YearRow(
                year=year,
                adoption=adoption,
                gross_benefit=gross_benefit,
                cost=cost,
                depreciation=depreciation,
                ebit=ebit,
                tax=tax,
                nopat=nopat,
                free_cash_flow=free_cash_flow,
            )
        )

    return OptionResult(option=option, rows=rows, discount_rate=assumptions.discount_rate)


def rank(results: Iterable[OptionResult]) -> list[OptionResult]:
    """Highest NPV first. Ties broken by profitability index."""
    return sorted(
        results,
        key=lambda r: (r.npv, r.profitability_index or 0.0),
        reverse=True,
    )
