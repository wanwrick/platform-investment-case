"""Uncertainty: sensitivity, the decision tree, and Monte Carlo.

A single NPV is a point estimate dressed up as an answer. These three views ask
the questions a reviewer will ask anyway. What has to be true for this to be
right. What happens if adoption stalls. How often does the recommendation lose.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, replace
from typing import Callable

from .model import AdoptionCurve, Assumptions, Option, OptionResult, build_schedule


# --- One-way and two-way sensitivity ------------------------------------------


def with_adoption_ceiling(option: Option, ceiling: float) -> Option:
    return replace(option, adoption=replace(option.adoption, ceiling=ceiling))


def with_benefit_scale(option: Option, scale: float) -> Option:
    """Scale every benefit driver by the same factor."""
    benefits = option.benefits
    scaled = replace(
        benefits,
        engineering_hours_saved=benefits.engineering_hours_saved * scale,
        licences_decommissioned=benefits.licences_decommissioned * scale,
        incidents_avoided=benefits.incidents_avoided * scale,
        analyst_hours_saved=benefits.analyst_hours_saved * scale,
        legacy_run_cost_avoided=benefits.legacy_run_cost_avoided * scale,
    )
    return replace(option, benefits=scaled)


def with_implementation_overrun(option: Option, scale: float) -> Option:
    """Apply an overrun to the build, not to the run.

    Overruns are an implementation phenomenon: the migration takes longer, the
    design phase needs another round. Scaling steady-state platform and run-team
    cost by the same factor would model a permanent tax on operating the thing
    for the rest of the horizon, which is a different and much larger claim.
    Getting this wrong makes every capital-heavy option look unviable.
    """
    costs = option.costs
    scaled = replace(
        costs,
        upfront_capex=costs.upfront_capex * scale,
        upfront_opex=costs.upfront_opex * scale,
        migration_cost_per_year=[c * scale for c in costs.migration_cost_per_year],
    )
    return replace(option, costs=scaled)


def with_run_cost_scale(option: Option, scale: float) -> Option:
    """Scale the recurring cost only. Used for the run-cost sensitivity."""
    costs = option.costs
    scaled = replace(
        costs,
        annual_platform_cost=costs.annual_platform_cost * scale,
        annual_run_team_cost=costs.annual_run_team_cost * scale,
    )
    return replace(option, costs=scaled)


def one_way_sensitivity(
    option: Option,
    assumptions: Assumptions,
    mutate: Callable[[Option, float], Option],
    values: list[float],
) -> list[tuple[float, float]]:
    """NPV at each value of one input, holding everything else fixed."""
    return [(v, build_schedule(mutate(option, v), assumptions).npv) for v in values]


def breakeven_adoption(
    option: Option,
    assumptions: Assumptions,
    *,
    lower: float = 0.0,
    upper: float = 1.0,
    tolerance: float = 1e-4,
) -> float | None:
    """The adoption ceiling at which this option's NPV crosses zero.

    This is the number worth taking into the room. Not "the NPV is 2.1M" but
    "we need 47% of teams on it, and today we have 12%."
    """
    npv_low = build_schedule(with_adoption_ceiling(option, lower), assumptions).npv
    npv_high = build_schedule(with_adoption_ceiling(option, upper), assumptions).npv
    if npv_low * npv_high > 0:
        return None

    while upper - lower > tolerance:
        mid = (lower + upper) / 2.0
        value = build_schedule(with_adoption_ceiling(option, mid), assumptions).npv
        if value * npv_low <= 0:
            upper = mid
        else:
            lower, npv_low = mid, value
    return (lower + upper) / 2.0


# --- Decision tree -------------------------------------------------------------


@dataclass(frozen=True)
class Branch:
    """One future state, its probability, and what it does to adoption."""

    name: str
    probability: float
    adoption_ceiling: float


@dataclass
class TreeOutcome:
    option: Option
    branches: list[tuple[Branch, float]]   # branch, NPV in that branch
    expected_npv: float
    downside_npv: float
    probability_of_loss: float


def decision_tree(
    option: Option, assumptions: Assumptions, branches: list[Branch]
) -> TreeOutcome:
    """Expected NPV across weighted futures, plus the downside.

    Expected value alone hides the shape. An option with a high mean and a 40%
    chance of a loss is a different proposition from one with the same mean and
    no losing branch, and only one of them survives a risk committee.
    """
    total = sum(b.probability for b in branches)
    if abs(total - 1.0) > 1e-6:
        raise ValueError(f"branch probabilities must sum to 1, got {total}")

    evaluated = [
        (b, build_schedule(with_adoption_ceiling(option, b.adoption_ceiling), assumptions).npv)
        for b in branches
    ]
    expected = sum(b.probability * value for b, value in evaluated)
    losing = [(b, v) for b, v in evaluated if v < 0]
    return TreeOutcome(
        option=option,
        branches=evaluated,
        expected_npv=expected,
        downside_npv=min(v for _, v in evaluated),
        probability_of_loss=sum(b.probability for b, _ in losing),
    )


# --- Monte Carlo ----------------------------------------------------------------


@dataclass
class SimulationResult:
    option_key: str
    samples: list[float]

    def percentile(self, p: float) -> float:
        if not self.samples:
            raise ValueError("no samples")
        ordered = sorted(self.samples)
        index = min(int(round(p * (len(ordered) - 1))), len(ordered) - 1)
        return ordered[index]

    @property
    def mean(self) -> float:
        return sum(self.samples) / len(self.samples)

    @property
    def probability_positive(self) -> float:
        return sum(1 for s in self.samples if s > 0) / len(self.samples)

    @property
    def p10(self) -> float:
        return self.percentile(0.10)

    @property
    def p50(self) -> float:
        return self.percentile(0.50)

    @property
    def p90(self) -> float:
        return self.percentile(0.90)


def _triangular(rng: random.Random, low: float, mode: float, high: float) -> float:
    """Triangular, because three-point estimates are what people can actually give.

    Nobody can state the standard deviation of a migration cost. Worst case,
    most likely, best case is a question a delivery lead can answer.
    """
    # random.triangular takes (low, high, mode), not (low, mode, high).
    return rng.triangular(low, high, mode)


def monte_carlo(
    option: Option,
    assumptions: Assumptions,
    *,
    trials: int = 5_000,
    adoption_range: tuple[float, float, float],
    benefit_scale_range: tuple[float, float, float],
    cost_scale_range: tuple[float, float, float],
    seed: int = 20260916,
) -> SimulationResult:
    """Sample adoption, benefit realization, and cost overrun together.

    Sampling them jointly is the point. Treating each as an independent
    one-way sensitivity understates the tail, because the world where adoption
    stalls is usually also the world where the migration ran over.
    """
    rng = random.Random(seed)
    samples: list[float] = []

    for _ in range(trials):
        ceiling = _triangular(rng, *adoption_range)
        benefit = _triangular(rng, *benefit_scale_range)
        cost = _triangular(rng, *cost_scale_range)

        candidate = with_adoption_ceiling(option, max(0.0, min(1.0, ceiling)))
        candidate = with_benefit_scale(candidate, max(0.0, benefit))
        candidate = with_implementation_overrun(candidate, max(0.0, cost))
        samples.append(build_schedule(candidate, assumptions).npv)

    return SimulationResult(option_key=option.key, samples=samples)


def probability_option_wins(
    results: dict[str, SimulationResult],
) -> dict[str, float]:
    """Share of trials in which each option has the highest NPV.

    Run on simulations sharing a seed, so trial i draws the same world for
    every option and the comparison is like for like.
    """
    keys = list(results)
    if not keys:
        return {}
    trials = len(results[keys[0]].samples)
    wins = {key: 0 for key in keys}
    for i in range(trials):
        best = max(keys, key=lambda k: results[k].samples[i])
        wins[best] += 1
    return {key: count / trials for key, count in wins.items()}


def crossover_adoption(
    challenger: Option,
    incumbent: Option,
    assumptions: Assumptions,
    *,
    lower: float = 0.0,
    upper: float = 1.0,
    tolerance: float = 1e-4,
) -> float | None:
    """The adoption level at which the challenger overtakes the incumbent.

    This turns "build has a higher NPV" into a condition of approval. The
    ambitious option is worth more only above some adoption level, and that
    level is a number the sponsor can be held to at a review gate.

    Both options are moved to the same ceiling, because the comparison is about
    a shared future, not about each option's own optimistic assumption.
    """

    def gap(ceiling: float) -> float:
        a = build_schedule(with_adoption_ceiling(challenger, ceiling), assumptions).npv
        b = build_schedule(with_adoption_ceiling(incumbent, ceiling), assumptions).npv
        return a - b

    gap_low, gap_high = gap(lower), gap(upper)
    if gap_low * gap_high > 0:
        return None

    while upper - lower > tolerance:
        mid = (lower + upper) / 2.0
        value = gap(mid)
        if value * gap_low <= 0:
            upper = mid
        else:
            lower, gap_low = mid, value
    return (lower + upper) / 2.0
