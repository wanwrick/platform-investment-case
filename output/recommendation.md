# Platform investment: build, extend, or buy

*Generated 2026-09-16 from the scenarios directory. 7-year horizon, discounted at 8.55% WACC.*

## Recommendation

**Extend the existing warehouse, unless adoption can be committed in advance.** Build the lakehouse shows the higher NPV at $1.96M against $353K, and that gap is real. It is also the option least likely to collect it.

The point estimate assumes Build the lakehouse reaches its planned adoption. Weighted across the futures we actually think are likely it returns -$71K with a 65% chance of a loss, against $79K and 20% for Extend the existing warehouse. In simulation it is the better option in 21% of trials.

**The decision turns on one number.** Build the lakehouse is worth more than Extend the existing warehouse above **65% adoption** and worth less below it. Today that number is a forecast. Convert it into a commitment and the answer changes.

## Situation

Three paths were modelled over the same horizon, at the same discount rate, on the same unit costs.

| Option | Thesis | Capability ceiling | Switching cost |
|---|---|---|---|
| **Build the lakehouse** | Move onto a governed lakehouse and run it ourselves. Highest cost to get there, lowest cost to run, and the only option that can serve the streaming and ML use cases the warehouse cannot reach. | 95% | $320K |
| **Buy the managed vendor platform** | Take the vendor's managed platform. Fastest to value and the smallest run team, paid for with a subscription that scales with usage and a switching cost that grows every year we stay. | 78% | $740K |
| **Extend the existing warehouse** | Keep the warehouse and buy more of it. Cheapest to start and nothing to migrate, but compute cost compounds and the capability ceiling is real: streaming and ML stay out of reach. | 55% | $90K |

## The numbers

| Option | NPV | IRR | PI | Payback | Disc. payback | Investment | EAV |
|---|---:|---:|---:|---:|---:|---:|---:|
| Build the lakehouse | $1.96M | 24.5% | 2.28 | 4.0 yrs | 4.6 yrs | $1.53M | $384K |
| Buy the managed vendor platform | $625K | 21.9% | 2.14 | 3.8 yrs | 4.4 yrs | $550K | $122K |
| Extend the existing warehouse | $353K | n/a | 2.47 | 1.9 yrs | 2.1 yrs | $240K | $69K |

NPV ranks by total value created. Profitability index ranks by value per dollar committed, which matters when the options differ in size: Build the lakehouse asks for $1.53M up front and Extend the existing warehouse asks for $240K.

## Complication: the ranking is an adoption bet

Costs are committed early and are reasonably knowable. Benefits are not. Nearly all of them depend on how many teams actually move, and no business case can promise that. So the table above is a forecast of adoption wearing a forecast of value.

| Option | Breakeven adoption | Modelled peak | Headroom |
|---|---:|---:|---:|
| Build the lakehouse | 61% | 80% | 18% |
| Buy the managed vendor platform | 66% | 72% | 6% |
| Extend the existing warehouse | 50% | 55% | 5% |

### Weighted futures

Three adoption outcomes, weighted by how likely they are.

| Option | Expected NPV | Worst branch | Chance of a loss |
|---|---:|---:|---:|
| Extend the existing warehouse | $79K | -$1.07M | 20% |
| Build the lakehouse | -$71K | -$3.33M | 65% |
| Buy the managed vendor platform | -$623K | -$3.73M | 65% |

### Simulation

Adoption, benefit realization, and cost overrun are sampled together, on a shared seed so every option faces the same world in each trial. Sampling them separately would understate the tail: the world where adoption stalls is usually also the world where the migration ran over.

5,000 trials.

| Option | P10 | Median | P90 | Chance NPV > 0 | Chance it wins |
|---|---:|---:|---:|---:|---:|
| Extend the existing warehouse | -$584K | -$21K | $366K | 48% | 79% |
| Build the lakehouse | -$2.60M | -$861K | $763K | 25% | 21% |
| Buy the managed vendor platform | -$2.84M | -$1.14M | $417K | 17% | 0% |

## Resolution

Approve **Extend the existing warehouse** now. Hold Build the lakehouse open as a staged decision rather than rejecting it, because the one thing that makes it the better answer is something we can go and build.

**The staged version**

1. Spend two quarters turning adoption from a forecast into signed commitments. Build the lakehouse needs 61% of teams to clear its cost of capital and 65% to beat Extend the existing warehouse.
2. If committed adoption clears 65% at the gate, switch to Build the lakehouse. The upside is $1.61M over the horizon, which is worth two quarters of waiting for.
3. If it does not clear, Extend the existing warehouse was the right call and $1.53M was not committed to a migration nobody had asked for.

**What has to be true**

1. At least 50% of eligible teams migrate. Below that, even the cheap option fails to return its cost of capital.
2. Benefit realization holds near the modelled level. The simulation samples down to 70% realization, and the P10 of -$584K is what that looks like.
3. The capability ceiling does not bind sooner than modelled. Extend the existing warehouse is capped at 55% of the estate. The first workload it cannot serve is the day this decision reopens.

**What would change the answer**

- Signed adoption above 65% at the two-quarter gate. That is the trigger, and it belongs in the approval rather than in a footnote.
- A streaming or ML requirement landing inside the horizon. Extend the existing warehouse cannot serve it at any adoption level, and a capability gap never shows up in an NPV table until it is too late to act on.
- Switching cost of $90K. Proprietary storage. A later move pays the migration this option avoided, at a larger data volume.

**Next three actions**

1. Name the first three migrating teams and get their commitment in writing before any spend is approved. Adoption is the entire case.
2. Set the two-quarter gate at 65% committed adoption, with a named owner and a pre-agreed stop condition.
3. Price switching cost into the comparison explicitly. It appears on no vendor quote and it is the largest single difference between these options.

---

## Method

Discount rate is WACC at 8.55%, built from CAPM: cost of equity 10.33% at a beta of 1.15, cost of debt 6.0% tax-shielded at 26.5%, on 30% debt.

Free cash flow is NOPAT plus depreciation less capex. Depreciation is removed from the tax base and added back, because it shields tax without being a cash cost.

Adoption follows a logistic curve rather than a straight line. Platform adoption is slow while the first team proves it works, fast once there is a reference implementation, then flat against a ceiling.

Every figure here is illustrative and belongs to no employer. Regenerate with python run.py after editing the scenarios directory.

---

## Appendix: cash flow schedules

### Build the lakehouse

| Year | Adoption | Gross benefit | Cost | Depreciation | EBIT | Tax | Free cash flow |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 0 | 0% | $0K | $1.53M | $0K | $0K | $0K | -$1.53M |
| 1 | 10% | $409K | $1.58M | $230K | -$1.40M | -$371K | -$800K |
| 2 | 34% | $1.35M | $1.45M | $230K | -$336K | -$89K | -$17K |
| 3 | 63% | $2.50M | $1.32M | $230K | $958K | $254K | $934K |
| 4 | 76% | $3.03M | $1.26M | $230K | $1.54M | $407K | $1.36M |
| 5 | 79% | $3.17M | $1.30M | $230K | $1.63M | $433K | $1.43M |
| 6 | 80% | $3.19M | $1.34M | $0K | $1.85M | $491K | $1.36M |
| 7 | 80% | $3.20M | $1.39M | $0K | $1.81M | $481K | $1.33M |

### Buy the managed vendor platform

| Year | Adoption | Gross benefit | Cost | Depreciation | EBIT | Tax | Free cash flow |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 0 | 0% | $0K | $550K | $0K | $0K | $0K | -$550K |
| 1 | 19% | $656K | $1.61M | $48K | -$1.00M | -$265K | -$688K |
| 2 | 53% | $1.78M | $1.54M | $48K | $192K | $51K | $189K |
| 3 | 69% | $2.32M | $1.53M | $48K | $750K | $199K | $600K |
| 4 | 72% | $2.42M | $1.64M | $48K | $739K | $196K | $591K |
| 5 | 72% | $2.44M | $1.76M | $48K | $632K | $167K | $512K |
| 6 | 72% | $2.44M | $1.89M | $0K | $549K | $146K | $404K |
| 7 | 72% | $2.44M | $2.03M | $0K | $406K | $107K | $298K |

### Extend the existing warehouse

| Year | Adoption | Gross benefit | Cost | Depreciation | EBIT | Tax | Free cash flow |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 0 | 0% | $0K | $240K | $0K | $0K | $0K | -$240K |
| 1 | 27% | $439K | $470K | $36K | -$67K | -$18K | -$13K |
| 2 | 55% | $885K | $522K | $36K | $327K | $87K | $276K |
| 3 | 55% | $885K | $584K | $36K | $265K | $70K | $231K |
| 4 | 55% | $885K | $656K | $36K | $193K | $51K | $178K |
| 5 | 55% | $885K | $742K | $36K | $107K | $28K | $115K |
| 6 | 55% | $885K | $843K | $0K | $42K | $11K | $31K |
| 7 | 55% | $885K | $963K | $0K | -$78K | -$21K | -$57K |
