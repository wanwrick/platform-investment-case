"""The cash flow model and the uncertainty views.

The tests that matter here are the ones that pin down a modelling decision
someone could quietly reverse: that capability caps adoption rather than
discounting it, that depreciation is added back, and that an overrun hits the
build and not the run.
"""

from __future__ import annotations

import pytest

from investment_case.loader import (
    load_assumptions,
    load_branches,
    load_options,
    load_simulation_config,
)
from investment_case.memo import render
from investment_case.model import build_schedule, rank
from investment_case.uncertainty import (
    Branch,
    breakeven_adoption,
    crossover_adoption,
    decision_tree,
    monte_carlo,
    probability_option_wins,
    with_adoption_ceiling,
    with_implementation_overrun,
    with_run_cost_scale,
)


@pytest.fixture(scope="module")
def loaded():
    assumptions, raw = load_assumptions()
    options = {o.key: o for o in load_options()}
    return assumptions, options, raw


# --- loading ------------------------------------------------------------------


def test_all_three_options_load(loaded):
    _, options, _ = loaded
    assert set(options) == {"build", "extend", "buy"}


def test_unit_costs_are_shared_across_options(loaded):
    """No scenario may make itself look good by repricing an engineer hour."""
    _, options, _ = loaded
    rates = {o.benefits.fully_loaded_hourly_rate for o in options.values()}
    assert len(rates) == 1


def test_discount_rate_is_the_same_for_every_option(loaded):
    assumptions, options, _ = loaded
    rates = {build_schedule(o, assumptions).discount_rate for o in options.values()}
    assert len(rates) == 1


# --- adoption -------------------------------------------------------------------


def test_adoption_starts_at_zero_and_never_exceeds_the_ceiling(loaded):
    _, options, _ = loaded
    curve = options["build"].adoption
    assert curve.share(0) == 0.0
    assert all(curve.share(y) <= curve.ceiling for y in range(1, 30))


def test_adoption_is_monotonically_increasing(loaded):
    _, options, _ = loaded
    curve = options["build"].adoption
    shares = [curve.share(y) for y in range(1, 15)]
    assert all(b >= a for a, b in zip(shares, shares[1:]))


def test_capability_caps_adoption_rather_than_discounting_it(loaded):
    """Multiplying the two would penalise an option twice for one constraint."""
    assumptions, options, _ = loaded
    extend = options["extend"]
    assert extend.capability_ceiling < extend.adoption.ceiling
    result = build_schedule(extend, assumptions)
    assert result.peak_adoption == pytest.approx(extend.capability_ceiling)


def test_peak_adoption_is_capped_however_high_the_ceiling_goes(loaded):
    """Enthusiasm cannot buy capability.

    Raising the ceiling does still lift NPV, because a higher curve reaches the
    cap sooner and the benefit arrives earlier. What it cannot do is lift the
    peak: the platform serves what it can serve.
    """
    assumptions, options, _ = loaded
    extend = options["extend"]
    for ceiling in (0.70, 0.85, 0.99):
        result = build_schedule(with_adoption_ceiling(extend, ceiling), assumptions)
        assert result.peak_adoption == pytest.approx(extend.capability_ceiling)


# --- schedule mechanics ---------------------------------------------------------


def test_time_zero_is_the_outlay_and_earns_nothing(loaded):
    assumptions, options, _ = loaded
    row = build_schedule(options["build"], assumptions).rows[0]
    assert row.gross_benefit == 0.0
    assert row.free_cash_flow == -(
        options["build"].costs.upfront_capex + options["build"].costs.upfront_opex
    )


def test_schedule_covers_the_whole_horizon(loaded):
    assumptions, options, _ = loaded
    assert len(build_schedule(options["build"], assumptions).rows) == assumptions.horizon_years + 1


def test_depreciation_is_added_back_to_cash_flow(loaded):
    """It shields tax without being a cash cost. Omitting the add-back understates FCF."""
    assumptions, options, _ = loaded
    for row in build_schedule(options["build"], assumptions).rows[1:]:
        assert row.free_cash_flow == pytest.approx(row.nopat + row.depreciation)


def test_depreciation_stops_at_the_end_of_its_schedule(loaded):
    assumptions, options, _ = loaded
    rows = build_schedule(options["build"], assumptions).rows
    assert rows[assumptions.depreciation_years].depreciation > 0
    assert rows[assumptions.depreciation_years + 1].depreciation == 0.0


def test_depreciation_totals_the_capitalised_amount(loaded):
    assumptions, options, _ = loaded
    rows = build_schedule(options["build"], assumptions).rows
    assert sum(r.depreciation for r in rows) == pytest.approx(
        options["build"].costs.upfront_capex
    )


def test_a_loss_year_produces_a_tax_credit_not_a_zero(loaded):
    """In a profitable firm the loss shields tax elsewhere, so the effect is symmetric."""
    assumptions, options, _ = loaded
    rows = build_schedule(options["build"], assumptions).rows
    loss_years = [r for r in rows[1:] if r.ebit < 0]
    assert loss_years, "expected at least one loss year during the ramp"
    assert all(r.tax < 0 for r in loss_years)


def test_platform_cost_compounds(loaded):
    """The line that decides against extending the warehouse."""
    _, options, _ = loaded
    costs = options["extend"].costs
    assert costs.year_cost(7) > costs.year_cost(1)


# --- ranking --------------------------------------------------------------------


def test_ranking_is_by_npv_descending(loaded):
    assumptions, options, _ = loaded
    ranked = rank(build_schedule(o, assumptions) for o in options.values())
    assert [r.npv for r in ranked] == sorted((r.npv for r in ranked), reverse=True)


def test_the_ambitious_option_has_the_highest_point_npv(loaded):
    """The finding the memo is built on. If this flips, the memo changes with it."""
    assumptions, options, _ = loaded
    ranked = rank(build_schedule(o, assumptions) for o in options.values())
    assert ranked[0].option.key == "build"


# --- breakeven and crossover -----------------------------------------------------


def test_npv_is_zero_at_the_breakeven_adoption(loaded):
    assumptions, options, _ = loaded
    for key in ("build", "buy"):
        ceiling = breakeven_adoption(options[key], assumptions)
        assert ceiling is not None
        at_breakeven = build_schedule(with_adoption_ceiling(options[key], ceiling), assumptions)
        assert at_breakeven.npv == pytest.approx(0.0, abs=5_000)


def test_two_options_are_worth_the_same_at_their_crossover(loaded):
    assumptions, options, _ = loaded
    ceiling = crossover_adoption(options["build"], options["extend"], assumptions)
    assert ceiling is not None
    a = build_schedule(with_adoption_ceiling(options["build"], ceiling), assumptions).npv
    b = build_schedule(with_adoption_ceiling(options["extend"], ceiling), assumptions).npv
    assert a == pytest.approx(b, abs=5_000)


def test_the_ambitious_option_wins_above_the_crossover_and_loses_below(loaded):
    assumptions, options, _ = loaded
    ceiling = crossover_adoption(options["build"], options["extend"], assumptions)
    assert ceiling is not None

    def gap(at: float) -> float:
        return (
            build_schedule(with_adoption_ceiling(options["build"], at), assumptions).npv
            - build_schedule(with_adoption_ceiling(options["extend"], at), assumptions).npv
        )

    assert gap(ceiling + 0.15) > 0
    assert gap(ceiling - 0.15) < 0


# --- decision tree ----------------------------------------------------------------


def test_branch_probabilities_must_sum_to_one(loaded):
    assumptions, options, _ = loaded
    bad = [Branch("a", 0.5, 0.8), Branch("b", 0.2, 0.3)]
    with pytest.raises(ValueError, match="sum to 1"):
        decision_tree(options["build"], assumptions, bad)


def test_expected_npv_lies_between_the_best_and_worst_branch(loaded):
    assumptions, options, _ = loaded
    outcome = decision_tree(options["build"], assumptions, load_branches())
    values = [v for _, v in outcome.branches]
    assert min(values) <= outcome.expected_npv <= max(values)
    assert outcome.downside_npv == pytest.approx(min(values))


def test_loss_probability_matches_the_losing_branches(loaded):
    assumptions, options, _ = loaded
    outcome = decision_tree(options["build"], assumptions, load_branches())
    expected = sum(b.probability for b, v in outcome.branches if v < 0)
    assert outcome.probability_of_loss == pytest.approx(expected)


# --- overruns ----------------------------------------------------------------------


def test_overrun_hits_the_build_and_not_the_run(loaded):
    """Scaling 7 years of run cost by an overrun factor is a different, larger claim."""
    _, options, _ = loaded
    stressed = with_implementation_overrun(options["build"], 1.5)
    assert stressed.costs.upfront_capex > options["build"].costs.upfront_capex
    assert stressed.costs.annual_platform_cost == options["build"].costs.annual_platform_cost
    assert stressed.costs.annual_run_team_cost == options["build"].costs.annual_run_team_cost


def test_run_cost_scaling_leaves_the_build_alone(loaded):
    _, options, _ = loaded
    stressed = with_run_cost_scale(options["build"], 1.5)
    assert stressed.costs.upfront_capex == options["build"].costs.upfront_capex
    assert stressed.costs.annual_platform_cost > options["build"].costs.annual_platform_cost


def test_an_overrun_lowers_npv(loaded):
    assumptions, options, _ = loaded
    base = build_schedule(options["build"], assumptions).npv
    stressed = build_schedule(with_implementation_overrun(options["build"], 1.4), assumptions).npv
    assert stressed < base


# --- simulation ---------------------------------------------------------------------


def test_simulation_is_reproducible(loaded):
    assumptions, options, _ = loaded
    config = {**load_simulation_config(), "trials": 300}
    first = monte_carlo(options["build"], assumptions, **config)
    second = monte_carlo(options["build"], assumptions, **config)
    assert first.samples == second.samples


def test_percentiles_are_ordered(loaded):
    assumptions, options, _ = loaded
    sim = monte_carlo(options["build"], assumptions, **{**load_simulation_config(), "trials": 500})
    assert sim.p10 <= sim.p50 <= sim.p90


def test_win_rates_sum_to_one(loaded):
    assumptions, options, _ = loaded
    config = {**load_simulation_config(), "trials": 300}
    sims = {k: monte_carlo(o, assumptions, **config) for k, o in options.items()}
    assert sum(probability_option_wins(sims).values()) == pytest.approx(1.0)


def test_every_option_faces_the_same_world_in_a_trial(loaded):
    """Shared seed. Without it the comparison is three unrelated experiments."""
    assumptions, options, _ = loaded
    config = {**load_simulation_config(), "trials": 200}
    sims = {k: monte_carlo(o, assumptions, **config) for k, o in options.items()}
    assert len({len(s.samples) for s in sims.values()}) == 1


# --- memo ----------------------------------------------------------------------------


def test_memo_renders_and_names_its_recommendation(loaded):
    assumptions, options, _ = loaded
    ranked = rank(build_schedule(o, assumptions) for o in options.values())
    branches = load_branches()
    trees = {k: decision_tree(o, assumptions, branches) for k, o in options.items()}
    config = {**load_simulation_config(), "trials": 300}
    sims = {k: monte_carlo(o, assumptions, **config) for k, o in options.items()}
    wins = probability_option_wins(sims)
    breakevens = {k: breakeven_adoption(o, assumptions) for k, o in options.items()}
    safe = max(trees, key=lambda k: trees[k].expected_npv)
    crossovers = {
        k: (None if k == safe else crossover_adoption(o, options[safe], assumptions))
        for k, o in options.items()
    }

    memo = render(ranked, assumptions, trees, sims, wins, breakevens, crossovers)

    assert memo.startswith("# Platform investment")
    assert "## Recommendation" in memo
    assert "## Resolution" in memo
    # The recommendation must appear before the evidence, not after it.
    assert memo.index("## Recommendation") < memo.index("## The numbers")


def test_memo_contains_no_em_dash(loaded):
    """House style, and the one thing a reader notices in a generated document."""
    assumptions, options, _ = loaded
    ranked = rank(build_schedule(o, assumptions) for o in options.values())
    branches = load_branches()
    trees = {k: decision_tree(o, assumptions, branches) for k, o in options.items()}
    config = {**load_simulation_config(), "trials": 100}
    sims = {k: monte_carlo(o, assumptions, **config) for k, o in options.items()}
    memo = render(
        ranked,
        assumptions,
        trees,
        sims,
        probability_option_wins(sims),
        {k: breakeven_adoption(o, assumptions) for k, o in options.items()},
    )
    assert "—" not in memo


def test_depreciation_longer_than_the_horizon_is_refused():
    """Otherwise the unbooked tail silently drops part of the tax shield."""
    from investment_case.finance import CapitalStructure
    from investment_case.model import Assumptions

    structure = CapitalStructure(0.04, 0.055, 1.15, 0.06, 0.30, 0.265)
    with pytest.raises(ValueError, match="exceeds"):
        Assumptions(horizon_years=5, capital_structure=structure, depreciation_years=7)


def test_memo_renders_when_an_option_has_no_upfront_outlay():
    """profitability_index is None with no outlay; the memo must not crash on it."""
    from investment_case.memo import pi_text

    assert pi_text(None) == "n/a"
    assert pi_text(1.2345) == "1.23"
