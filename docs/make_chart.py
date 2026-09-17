"""Generate docs/sensitivity.svg from the model.

NPV against adoption for every option, with the breakeven line and the
crossover marked. The chart is built from the same code that writes the memo,
so it cannot show something the analysis does not say.

    python docs/make_chart.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from investment_case.loader import load_assumptions, load_options  # noqa: E402
from investment_case.model import build_schedule  # noqa: E402
from investment_case.uncertainty import (  # noqa: E402
    crossover_adoption,
    with_adoption_ceiling,
)

WIDTH, HEIGHT = 1240, 620
PAD_L, PAD_R, PAD_T, PAD_B = 96, 268, 132, 100

CHARCOAL = "#252525"
PARCHMENT = "#F1ECDC"
RED = "#E22D00"
MUTED = "rgba(241,236,220,0.55)"
GRID = "rgba(241,236,220,0.13)"

SERIES_STYLE = {
    "build": (RED, "none", 3.0),
    "buy": (PARCHMENT, "none", 2.0),
    "extend": (PARCHMENT, "7 5", 2.0),
}


def main() -> None:
    assumptions, _ = load_assumptions()
    options = {o.key: o for o in load_options()}

    steps = [i / 100 for i in range(20, 96)]
    curves = {
        key: [
            (s, build_schedule(with_adoption_ceiling(opt, s), assumptions).npv)
            for s in steps
        ]
        for key, opt in options.items()
    }

    crossover = crossover_adoption(options["build"], options["extend"], assumptions)

    values = [v for series in curves.values() for _, v in series]
    y_min, y_max = min(values), max(values)
    span = y_max - y_min
    y_min -= span * 0.08
    y_max += span * 0.08

    def x_of(share: float) -> float:
        return PAD_L + (share - steps[0]) / (steps[-1] - steps[0]) * (WIDTH - PAD_L - PAD_R)

    def y_of(value: float) -> float:
        return HEIGHT - PAD_B - (value - y_min) / (y_max - y_min) * (HEIGHT - PAD_T - PAD_B)

    parts: list[str] = []
    add = parts.append

    add(f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" '
        f'viewBox="0 0 {WIDTH} {HEIGHT}" font-family="Fira Sans, Segoe UI, sans-serif">')
    add(f'<rect width="{WIDTH}" height="{HEIGHT}" fill="{CHARCOAL}"/>')

    # Titles
    add(f'<text x="{PAD_L}" y="38" fill="{RED}" font-size="13" font-weight="700" '
        f'letter-spacing="2">NPV AGAINST ADOPTION</text>')
    add(f'<text x="{PAD_L}" y="66" fill="{PARCHMENT}" font-size="25" font-weight="700">'
        f'The decision is an adoption bet, not an architecture choice</text>')

    # Grid and y labels
    ticks = 6
    for i in range(ticks + 1):
        value = y_min + (y_max - y_min) * i / ticks
        y = y_of(value)
        add(f'<line x1="{PAD_L}" y1="{y:.1f}" x2="{WIDTH - PAD_R}" y2="{y:.1f}" '
            f'stroke="{GRID}" stroke-width="1"/>')
        add(f'<text x="{PAD_L - 12}" y="{y + 4:.1f}" fill="{MUTED}" font-size="12" '
            f'text-anchor="end">${value / 1e6:.1f}M</text>')

    # x labels
    for share in [0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]:
        x = x_of(share)
        add(f'<text x="{x:.1f}" y="{HEIGHT - PAD_B + 24:.1f}" fill="{MUTED}" '
            f'font-size="12" text-anchor="middle">{share * 100:.0f}%</text>')
    add(f'<text x="{(PAD_L + WIDTH - PAD_R) / 2:.1f}" y="{HEIGHT - PAD_B + 50:.1f}" '
        f'fill="{MUTED}" font-size="12.5" text-anchor="middle">'
        f'Share of eligible teams migrated</text>')

    # Zero line: the breakeven every curve crosses
    if y_min < 0 < y_max:
        zero = y_of(0.0)
        add(f'<line x1="{PAD_L}" y1="{zero:.1f}" x2="{WIDTH - PAD_R}" y2="{zero:.1f}" '
            f'stroke="{PARCHMENT}" stroke-width="1.5" stroke-opacity="0.45"/>')
        add(f'<text x="{WIDTH - PAD_R - 8}" y="{zero - 9:.1f}" fill="{MUTED}" '
            f'font-size="11.5" text-anchor="end">NPV = 0, returns the cost of capital</text>')

    # Crossover marker
    if crossover is not None:
        x = x_of(crossover)
        add(f'<line x1="{x:.1f}" y1="{PAD_T - 14}" x2="{x:.1f}" y2="{HEIGHT - PAD_B}" '
            f'stroke="{RED}" stroke-width="1.5" stroke-dasharray="4 4" stroke-opacity="0.8"/>')
        add(f'<rect x="{x - 76:.1f}" y="{PAD_T - 36}" width="152" height="22" fill="{RED}"/>')
        add(f'<text x="{x:.1f}" y="{PAD_T - 21}" fill="{PARCHMENT}" font-size="12" '
            f'font-weight="700" text-anchor="middle">'
            f'Crossover {crossover * 100:.0f}%</text>')

    # Axes
    add(f'<line x1="{PAD_L}" y1="{PAD_T - 14}" x2="{PAD_L}" y2="{HEIGHT - PAD_B}" '
        f'stroke="{MUTED}" stroke-width="1"/>')

    # Curves
    for key, series in curves.items():
        colour, dash, width = SERIES_STYLE[key]
        points = " ".join(f"{x_of(s):.1f},{y_of(v):.1f}" for s, v in series)
        add(f'<polyline points="{points}" fill="none" stroke="{colour}" '
            f'stroke-width="{width}" stroke-dasharray="{dash}" '
            f'stroke-linejoin="round" stroke-linecap="round"/>')

    # Legend, in the empty corner
    legend_x = WIDTH - PAD_R + 18
    legend_y = PAD_T + 10
    add(f'<text x="{legend_x}" y="{legend_y - 14}" fill="{RED}" font-size="11" '
        f'font-weight="700" letter-spacing="1.4">OPTION</text>')
    for i, key in enumerate(("build", "buy", "extend")):
        colour, dash, width = SERIES_STYLE[key]
        y = legend_y + i * 44
        add(f'<line x1="{legend_x}" y1="{y + 5}" x2="{legend_x + 26}" y2="{y + 5}" '
            f'stroke="{colour}" stroke-width="{width}" stroke-dasharray="{dash}"/>')
        add(f'<text x="{legend_x}" y="{y + 26}" fill="{PARCHMENT}" font-size="12.5">'
            f'{options[key].name}</text>')
        peak = build_schedule(options[key], assumptions).peak_adoption
        add(f'<text x="{legend_x}" y="{y + 41}" fill="{MUTED}" font-size="11">'
            f'peak {peak * 100:.0f}% adoption</text>')

    # Reading note
    add(f'<text x="{PAD_L}" y="{HEIGHT - 22}" fill="{MUTED}" font-size="11.5">'
        f'Every option is moved to the same adoption level, so the comparison is a '
        f'shared future rather than each option&#8217;s own forecast.</text>')

    add("</svg>")

    out = Path(__file__).parent / "sensitivity.svg"
    out.write_text("\n".join(parts), encoding="utf-8")
    print(f"Wrote {out}")
    if crossover is not None:
        print(f"Crossover at {crossover * 100:.1f}% adoption")


if __name__ == "__main__":
    main()
