"""Load scenarios from YAML into the model's dataclasses.

Unit costs live once in assumptions.yaml and are injected into every option, so
no scenario can make itself look good by quietly repricing an engineer hour.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from .finance import CapitalStructure
from .model import AdoptionCurve, Assumptions, BenefitDrivers, CostProfile, Option
from .uncertainty import Branch

SCENARIO_DIR = Path(__file__).resolve().parents[1] / "scenarios"
ASSUMPTIONS_FILE = "assumptions.yaml"


def _read(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def load_assumptions(directory: Path = SCENARIO_DIR) -> tuple[Assumptions, dict[str, Any]]:
    """Return the modelling assumptions and the raw config beside them."""
    raw = _read(directory / ASSUMPTIONS_FILE)
    structure = CapitalStructure(**raw["capital_structure"])
    assumptions = Assumptions(
        horizon_years=int(raw["horizon_years"]),
        capital_structure=structure,
        depreciation_years=int(raw["depreciation_years"]),
    )
    return assumptions, raw


def load_option(path: Path, unit_costs: dict[str, float]) -> Option:
    raw = _read(path)
    costs = CostProfile(
        upfront_capex=float(raw["costs"]["upfront_capex"]),
        upfront_opex=float(raw["costs"]["upfront_opex"]),
        annual_platform_cost=float(raw["costs"]["annual_platform_cost"]),
        annual_platform_cost_growth=float(raw["costs"]["annual_platform_cost_growth"]),
        annual_run_team_cost=float(raw["costs"]["annual_run_team_cost"]),
        migration_cost_per_year=[float(c) for c in raw["costs"].get("migration_cost_per_year", [])],
    )
    benefits = BenefitDrivers(
        engineering_hours_saved=float(raw["benefits"]["engineering_hours_saved"]),
        fully_loaded_hourly_rate=float(unit_costs["fully_loaded_engineer_hourly"]),
        licences_decommissioned=float(raw["benefits"]["licences_decommissioned"]),
        licence_unit_cost=float(unit_costs["bi_licence_annual"]),
        incidents_avoided=float(raw["benefits"]["incidents_avoided"]),
        incident_cost=float(unit_costs["major_incident"]),
        analyst_hours_saved=float(raw["benefits"]["analyst_hours_saved"]),
        analyst_hourly_rate=float(unit_costs["analyst_hourly"]),
        legacy_run_cost_avoided=float(raw["benefits"].get("legacy_run_cost_avoided", 0.0)),
    )
    adoption = AdoptionCurve(
        ceiling=float(raw["adoption"]["ceiling"]),
        midpoint_year=float(raw["adoption"]["midpoint_year"]),
        steepness=float(raw["adoption"]["steepness"]),
    )
    return Option(
        key=raw["key"],
        name=raw["name"],
        thesis=" ".join(raw["thesis"].split()),
        costs=costs,
        benefits=benefits,
        adoption=adoption,
        capability_ceiling=float(raw["capability_ceiling"]),
        switching_cost=float(raw["switching_cost"]),
        lock_in_note=" ".join(raw.get("lock_in_note", "").split()),
    )


def load_options(directory: Path = SCENARIO_DIR) -> list[Option]:
    _, raw = load_assumptions(directory)
    unit_costs = raw["unit_costs"]
    paths = sorted(p for p in directory.glob("*.yaml") if p.name != ASSUMPTIONS_FILE)
    return [load_option(path, unit_costs) for path in paths]


def load_branches(directory: Path = SCENARIO_DIR) -> list[Branch]:
    _, raw = load_assumptions(directory)
    return [
        Branch(
            name=entry["name"],
            probability=float(entry["probability"]),
            adoption_ceiling=float(entry["adoption_ceiling"]),
        )
        for entry in raw["decision_tree"]
    ]


def load_simulation_config(directory: Path = SCENARIO_DIR) -> dict[str, Any]:
    _, raw = load_assumptions(directory)
    sim = raw["simulation"]
    return {
        "trials": int(sim["trials"]),
        "seed": int(sim["seed"]),
        "adoption_range": tuple(float(v) for v in sim["adoption_ceiling"]),
        "benefit_scale_range": tuple(float(v) for v in sim["benefit_realization"]),
        "cost_scale_range": tuple(float(v) for v in sim["cost_overrun"]),
    }
