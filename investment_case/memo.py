"""Render the analysis as a recommendation memo.

Structure is SCR: situation, complication, resolution, with the recommendation
in the first line. The memo is generated from the model, so it cannot drift
from the numbers it cites. Change an assumption and the prose changes with it.
"""

from __future__ import annotations

from datetime import date

from .model import Assumptions, OptionResult
from .uncertainty import SimulationResult, TreeOutcome


def money(value: float) -> str:
    """Round to the nearest thousand. Cents imply a precision nobody has."""
    sign = "-" if value < 0 else ""
    magnitude = abs(value)
    if magnitude >= 1_000_000:
        return f"{sign}${magnitude / 1_000_000:.2f}M"
    return f"{sign}${magnitude / 1_000:.0f}K"


def pct(value: float | None, places: int = 1) -> str:
    return "n/a" if value is None else f"{value * 100:.{places}f}%"


def years(value: float | None) -> str:
    return "never" if value is None else f"{value:.1f} yrs"


def pi_text(value: float | None) -> str:
    """PI is undefined when there is no upfront outlay to divide by."""
    return "n/a" if value is None else f"{value:.2f}"


def render(
    ranked: list[OptionResult],
    assumptions: Assumptions,
    trees: dict[str, TreeOutcome],
    simulations: dict[str, SimulationResult],
    win_rates: dict[str, float],
    breakevens: dict[str, float | None],
    crossovers: dict[str, float | None] | None = None,
) -> str:
    winner = ranked[0]
    runner_up = ranked[1]
    rate = assumptions.discount_rate
    sim_winner = simulations[winner.option.key]

    # The decision tree can disagree with the point estimate. When it does,
    # that disagreement is the most useful sentence in the memo.
    tree_ranked = sorted(trees.values(), key=lambda t: t.expected_npv, reverse=True)
    tree_winner = tree_ranked[0]
    tree_disagrees = tree_winner.option.key != winner.option.key

    # So does the simulation, which is the one that accounts for cost overrun.
    sim_ranked = sorted(win_rates.items(), key=lambda kv: kv[1], reverse=True)
    sim_winner_key = sim_ranked[0][0]
    sim_disagrees = sim_winner_key != winner.option.key

    crossovers = crossovers or {}
    recommended_result = next(
        (r for r in ranked if r.option.key == tree_winner.option.key), winner
    )
    recommended = recommended_result.option
    crossover = crossovers.get(winner.option.key)

    lines: list[str] = []
    add = lines.append

    add("# Platform investment: build, extend, or buy")
    add("")
    add(f"*Generated {date.today().isoformat()} from the scenarios directory. "
        f"{assumptions.horizon_years}-year horizon, discounted at {pct(rate, 2)} WACC.*")
    add("")

    # --- Recommendation -------------------------------------------------------
    add("## Recommendation")
    add("")
    if tree_disagrees or sim_disagrees:
        add(f"**{recommended.name}, unless adoption can be committed in advance.** "
            f"{winner.option.name} shows the higher NPV at {money(winner.npv)} against "
            f"{money(recommended_result.npv)}, and that gap is real. It is also the "
            f"option least likely to collect it.")
        add("")
        add(f"The point estimate assumes {winner.option.name} reaches its planned "
            f"adoption. Weighted across the futures we actually think are likely it "
            f"returns {money(trees[winner.option.key].expected_npv)} with a "
            f"{pct(trees[winner.option.key].probability_of_loss, 0)} chance of a loss, "
            f"against {money(tree_winner.expected_npv)} and "
            f"{pct(tree_winner.probability_of_loss, 0)} for {recommended.name}. "
            f"In simulation it is the better option in "
            f"{pct(win_rates[winner.option.key], 0)} of trials.")
        add("")
        if crossover is not None:
            add(f"**The decision turns on one number.** {winner.option.name} is worth "
                f"more than {recommended.name} above **{pct(crossover, 0)} adoption** "
                f"and worth less below it. Today that number is a forecast. Convert it "
                f"into a commitment and the answer changes.")
    else:
        add(f"**{winner.option.name}. NPV {money(winner.npv)} at a {pct(rate, 2)} "
            f"discount rate, against {money(runner_up.npv)} for {runner_up.option.name}.**")
        add("")
        add(f"It also wins on the two views that do not assume the plan lands: "
            f"expected NPV across weighted futures, and {pct(win_rates[winner.option.key], 0)} "
            f"of simulated trials.")
    add("")

    # --- Situation ------------------------------------------------------------
    add("## Situation")
    add("")
    add("Three paths were modelled over the same horizon, at the same discount "
        "rate, on the same unit costs.")
    add("")
    add("| Option | Thesis | Capability ceiling | Switching cost |")
    add("|---|---|---|---|")
    for result in ranked:
        option = result.option
        add(f"| **{option.name}** | {option.thesis} | {pct(option.capability_ceiling, 0)} "
            f"| {money(option.switching_cost)} |")
    add("")

    # --- The numbers ----------------------------------------------------------
    add("## The numbers")
    add("")
    add("| Option | NPV | IRR | PI | Payback | Disc. payback | Investment | EAV |")
    add("|---|---:|---:|---:|---:|---:|---:|---:|")
    for result in ranked:
        add(
            f"| {result.option.name} | {money(result.npv)} | {pct(result.irr)} "
            f"| {pi_text(result.profitability_index)} | {years(result.payback)} "
            f"| {years(result.discounted_payback)} | {money(result.total_investment)} "
            f"| {money(result.equivalent_annual_value)} |"
        )
    add("")
    add(f"NPV ranks by total value created. Profitability index ranks by value per "
        f"dollar committed, which matters when the options differ in size: "
        f"{ranked[0].option.name} asks for {money(ranked[0].total_investment)} up front "
        f"and {ranked[-1].option.name} asks for {money(ranked[-1].total_investment)}.")
    add("")

    # --- Complication ---------------------------------------------------------
    add("## Complication: the ranking is an adoption bet")
    add("")
    add("Costs are committed early and are reasonably knowable. Benefits are not. "
        "Nearly all of them depend on how many teams actually move, and no "
        "business case can promise that. So the table above is a forecast of "
        "adoption wearing a forecast of value.")
    add("")
    add("| Option | Breakeven adoption | Modelled peak | Headroom |")
    add("|---|---:|---:|---:|")
    for result in ranked:
        be = breakevens.get(result.option.key)
        peak = result.peak_adoption
        headroom = "n/a" if be is None else pct(peak - be, 0)
        add(f"| {result.option.name} | {pct(be, 0) if be is not None else 'never breaks even'} "
            f"| {pct(peak, 0)} | {headroom} |")
    add("")

    # --- Weighted futures -----------------------------------------------------
    add("### Weighted futures")
    add("")
    add("Three adoption outcomes, weighted by how likely they are.")
    add("")
    add("| Option | Expected NPV | Worst branch | Chance of a loss |")
    add("|---|---:|---:|---:|")
    for outcome in tree_ranked:
        add(f"| {outcome.option.name} | {money(outcome.expected_npv)} "
            f"| {money(outcome.downside_npv)} | {pct(outcome.probability_of_loss, 0)} |")
    add("")

    # --- Simulation -----------------------------------------------------------
    add("### Simulation")
    add("")
    config_note = (
        "Adoption, benefit realization, and cost overrun are sampled together, "
        "on a shared seed so every option faces the same world in each trial. "
        "Sampling them separately would understate the tail: the world where "
        "adoption stalls is usually also the world where the migration ran over."
    )
    add(config_note)
    add("")
    add(f"{len(sim_winner.samples):,} trials.")
    add("")
    add("| Option | P10 | Median | P90 | Chance NPV > 0 | Chance it wins |")
    add("|---|---:|---:|---:|---:|---:|")
    for key, share in sim_ranked:
        sim = simulations[key]
        add(f"| {_name(ranked, key)} | {money(sim.p10)} | {money(sim.p50)} "
            f"| {money(sim.p90)} | {pct(sim.probability_positive, 0)} | {pct(share, 0)} |")
    add("")

    # --- Resolution -----------------------------------------------------------
    add("## Resolution")
    add("")
    be = breakevens.get(recommended.key)
    add(f"Approve **{recommended.name}** now. Hold {winner.option.name} open as a "
        f"staged decision rather than rejecting it, because the one thing that makes "
        f"it the better answer is something we can go and build.")
    add("")
    add("**The staged version**")
    add("")
    if crossover is not None:
        upside = winner.npv - recommended_result.npv
        at_risk = winner.option.costs.upfront_capex + winner.option.costs.upfront_opex
        add(f"1. Spend two quarters turning adoption from a forecast into signed "
            f"commitments. {winner.option.name} needs "
            f"{pct(breakevens.get(winner.option.key), 0)} of teams to clear its cost of "
            f"capital and {pct(crossover, 0)} to beat {recommended.name}.")
        add(f"2. If committed adoption clears {pct(crossover, 0)} at the gate, switch to "
            f"{winner.option.name}. The upside is {money(upside)} over the horizon, "
            f"which is worth two quarters of waiting for.")
        add(f"3. If it does not clear, {recommended.name} was the right call and "
            f"{money(at_risk)} was not committed to a migration nobody had asked for.")
    add("")
    add("**What has to be true**")
    add("")
    if be is not None:
        add(f"1. At least {pct(be, 0)} of eligible teams migrate. Below that, even the "
            f"cheap option fails to return its cost of capital.")
    add(f"2. Benefit realization holds near the modelled level. The simulation samples "
        f"down to 70% realization, and the P10 of "
        f"{money(simulations[recommended.key].p10)} is what that looks like.")
    add(f"3. The capability ceiling does not bind sooner than modelled. "
        f"{recommended.name} is capped at {pct(recommended.capability_ceiling, 0)} of the "
        f"estate. The first workload it cannot serve is the day this decision reopens.")
    add("")
    add("**What would change the answer**")
    add("")
    add(f"- Signed adoption above {pct(crossover, 0) if crossover else 'the crossover'} "
        f"at the two-quarter gate. That is the trigger, and it belongs in the approval "
        f"rather than in a footnote.")
    add(f"- A streaming or ML requirement landing inside the horizon. "
        f"{recommended.name} cannot serve it at any adoption level, and a capability "
        f"gap never shows up in an NPV table until it is too late to act on.")
    if recommended.lock_in_note:
        add(f"- Switching cost of {money(recommended.switching_cost)}. "
            f"{recommended.lock_in_note}")
    add("")
    add("**Next three actions**")
    add("")
    add("1. Name the first three migrating teams and get their commitment in writing "
        "before any spend is approved. Adoption is the entire case.")
    add(f"2. Set the two-quarter gate at "
        f"{pct(crossover, 0) if crossover else 'the crossover adoption'} committed "
        f"adoption, with a named owner and a pre-agreed stop condition.")
    add("3. Price switching cost into the comparison explicitly. It appears on no "
        "vendor quote and it is the largest single difference between these options.")
    add("")
    add("---")
    add("")
    # --- Method ---------------------------------------------------------------
    add("## Method")
    add("")
    cs = assumptions.capital_structure
    add(f"Discount rate is WACC at {pct(rate, 2)}, built from CAPM: "
        f"cost of equity {pct(cs.risk_free_rate + cs.beta * cs.equity_risk_premium, 2)} "
        f"at a beta of {cs.beta}, cost of debt {pct(cs.cost_of_debt, 1)} "
        f"tax-shielded at {pct(cs.tax_rate, 1)}, on {pct(cs.debt_weight, 0)} debt.")
    add("")
    add("Free cash flow is NOPAT plus depreciation less capex. Depreciation is "
        "removed from the tax base and added back, because it shields tax "
        "without being a cash cost.")
    add("")
    add("Adoption follows a logistic curve rather than a straight line. Platform "
        "adoption is slow while the first team proves it works, fast once there "
        "is a reference implementation, then flat against a ceiling.")
    add("")
    add("Every figure here is illustrative and belongs to no employer. "
        "Regenerate with python run.py after editing the scenarios directory.")

    return "\n".join(line for line in lines if line is not None)


def _name(ranked: list[OptionResult], key: str) -> str:
    return next(r.option.name for r in ranked if r.option.key == key)


def render_schedule(result: OptionResult) -> str:
    """The year-by-year cash flow table, for the appendix."""
    lines = [
        f"### {result.option.name}",
        "",
        "| Year | Adoption | Gross benefit | Cost | Depreciation | EBIT | Tax | Free cash flow |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in result.rows:
        lines.append(
            f"| {row.year} | {pct(row.adoption, 0)} | {money(row.gross_benefit)} "
            f"| {money(row.cost)} | {money(row.depreciation)} | {money(row.ebit)} "
            f"| {money(row.tax)} | {money(row.free_cash_flow)} |"
        )
    lines.append("")
    return "\n".join(lines)
