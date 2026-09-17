"""Run the analysis and write the recommendation memo.

    python run.py                 # writes output/recommendation.md
    python run.py --summary       # prints the headline table and stops
    python run.py --trials 20000  # more simulation trials
"""

from __future__ import annotations

import argparse
from pathlib import Path

from investment_case.loader import (
    SCENARIO_DIR,
    load_assumptions,
    load_branches,
    load_options,
    load_simulation_config,
)
from investment_case.memo import money, pct, render, render_schedule, years
from investment_case.model import build_schedule, rank
from investment_case.uncertainty import (
    breakeven_adoption,
    crossover_adoption,
    decision_tree,
    monte_carlo,
    probability_option_wins,
)

OUTPUT_DIR = Path(__file__).resolve().parent / "output"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenarios", type=Path, default=SCENARIO_DIR)
    parser.add_argument("--out", type=Path, default=OUTPUT_DIR / "recommendation.md")
    parser.add_argument("--trials", type=int, default=None, help="override simulation trials")
    parser.add_argument("--summary", action="store_true", help="print the table, write nothing")
    args = parser.parse_args()

    assumptions, _ = load_assumptions(args.scenarios)
    options = load_options(args.scenarios)
    branches = load_branches(args.scenarios)
    sim_config = load_simulation_config(args.scenarios)
    if args.trials:
        sim_config["trials"] = args.trials

    results = [build_schedule(option, assumptions) for option in options]
    ranked = rank(results)

    trees = {o.key: decision_tree(o, assumptions, branches) for o in options}
    breakevens = {o.key: breakeven_adoption(o, assumptions) for o in options}
    simulations = {o.key: monte_carlo(o, assumptions, **sim_config) for o in options}
    win_rates = probability_option_wins(simulations)

    # Each option measured against whichever one the risk-adjusted view prefers:
    # the adoption level at which the ambitious option stops being the expensive one.
    safe_key = max(trees, key=lambda k: trees[k].expected_npv)
    safe = next(o for o in options if o.key == safe_key)
    crossovers = {
        o.key: (None if o.key == safe_key else crossover_adoption(o, safe, assumptions))
        for o in options
    }

    if args.summary:
        print(f"Discount rate (WACC): {pct(assumptions.discount_rate, 2)}")
        print(f"{'Option':<34}{'NPV':>12}{'IRR':>9}{'Payback':>11}{'Breakeven':>12}{'Wins':>8}")
        for result in ranked:
            key = result.option.key
            be = breakevens[key]
            print(
                f"{result.option.name:<34}{money(result.npv):>12}{pct(result.irr):>9}"
                f"{years(result.payback):>11}"
                f"{(pct(be, 0) if be is not None else 'never'):>12}"
                f"{pct(win_rates[key], 0):>8}"
            )
        return 0

    memo = render(
        ranked, assumptions, trees, simulations, win_rates, breakevens, crossovers
    )
    appendix = "\n".join(
        ["", "---", "", "## Appendix: cash flow schedules", ""]
        + [render_schedule(r) for r in ranked]
    )

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(memo + "\n" + appendix, encoding="utf-8")
    print(f"Wrote {args.out}")
    print(f"Recommended: {ranked[0].option.name} on point estimate, "
          f"{max(win_rates, key=win_rates.get)} on simulated win rate")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
