"""
Net Worth Calculator V2 for Masters Programs
=============================================
Location-aware 12-year net worth calculator using:
  - Progressive tax brackets for ~36 countries + US state taxes
  - Real per-city living costs (student / single / family profiles)
  - Market mapping from primary_market field

Timeline: 12 calendar years total
  - Years 1-2: Study period (tuition + student living costs, no income)
  - Years 3-12: Post-grad work (work years 1-10)
  - Household: single until family_transition_year (default 5), then family

Net Worth Formula:
  Masters path:
    net_worth = Σ(yr 3-12)[after_tax_salary - living_cost]
              - tuition
              - Σ(yr 1-2)[student_living_cost]

  Baseline (stay in Pakistan, no masters):
    net_worth = Σ(yr 1-12)[after_tax_pakistan_salary - pakistan_living_cost]
    with single→family transition at year 5 (same as masters path)

  Net benefit = masters_net_worth - baseline_net_worth

Salary interpolation: Y1, Y5, Y10 post-grad data points with linear
interpolation. These represent work experience years, not calendar years.

All values in $K USD unless otherwise noted.
"""

import sqlite3
from typing import Optional

from config import (
    DB_PATH,
    get_db,
    BASELINE_ANNUAL_SALARY_USD_K,
    BASELINE_ANNUAL_GROWTH,
    MASTERS_TOTAL_YEARS,
    MASTERS_DEFAULT_FAMILY_YEAR,
    MASTERS_DEFAULT_DURATION,
)
from calculator_common import (
    interpolate_salary,
    avg_summary,
    calculate_pakistan_baseline,
)
from market_mapping import get_market_info, get_study_country_for_living_cost
from tax_data import calculate_annual_tax
from living_costs import (
    get_annual_living_cost,
    get_study_living_cost,
    get_pakistan_living_cost,
)

# ─── Configuration ───────────────────────────────────────────────────────────
# Constants imported from config.py for consistency:
# - MASTERS_TOTAL_YEARS (12): 2yr study + 10yr work
# - MASTERS_DEFAULT_FAMILY_YEAR (5): calendar year for single→family transition
# - MASTERS_DEFAULT_DURATION (2.0): default program duration

# Local aliases for backwards compatibility
DEFAULT_DURATION = MASTERS_DEFAULT_DURATION
FAMILY_TRANSITION_YEAR = MASTERS_DEFAULT_FAMILY_YEAR
TOTAL_YEARS = MASTERS_TOTAL_YEARS


# ─── Core Calculation Functions ──────────────────────────────────────────────


def calculate_baseline_networth(
    baseline_salary: Optional[float] = None,
    baseline_growth: Optional[float] = None,
    lifestyle: str = "frugal",
    family_transition_year: Optional[int] = None,
):
    """
    Calculate 12-year cumulative net worth on the no-masters baseline path.
    Staying in Pakistan with current salary + annual growth.
    Single living until family_transition_year, then family living.

    Args:
        baseline_salary: Override for baseline annual salary in $K USD.
        baseline_growth: Override for baseline annual growth rate.
        lifestyle: "frugal" or "comfortable" living cost tier.
        family_transition_year: Calendar year when household transitions to family
            (1-12, or 13 for never). Default: FAMILY_TRANSITION_YEAR (5).
    """
    return calculate_pakistan_baseline(
        total_years=TOTAL_YEARS,
        default_family_year=FAMILY_TRANSITION_YEAR,
        year_key="calendar_year",
        baseline_salary=baseline_salary,
        baseline_growth=baseline_growth,
        lifestyle=lifestyle,
        family_transition_year=family_transition_year,
    )


def calculate_program_networth(
    program: dict,
    baseline_total: Optional[float] = None,
    baseline_salary: Optional[float] = None,
    baseline_growth: Optional[float] = None,
    lifestyle: str = "frugal",
    family_transition_year: Optional[int] = None,
    aid_scenario: str = "no_aid",
) -> dict:
    """
    Calculate 12-year net worth for a specific masters program.

    Timeline:
      Calendar years 1-2: Study (pay tuition + student living, no income)
      Calendar years 3-12: Work years 1-10
      Household transitions from single to family at family_transition_year.

    Uses:
      - Market mapping to determine work country/city/state
      - Progressive tax brackets for the work country
      - Real living costs for study city (university country) and work city

    Args:
        lifestyle: "frugal" or "comfortable" living cost tier.
        family_transition_year: Calendar year when household transitions to family
            (1-12, or 13 for never). Default: FAMILY_TRANSITION_YEAR (5).
        aid_scenario: Financial aid scenario to apply:
            - "no_aid": Full sticker price tuition (conservative/current behavior)
            - "expected": Apply expected_aid_usd reduction (realistic estimate)
            - "best_case": Apply best_case_aid_usd reduction (optimistic but achievable)
    """
    if family_transition_year is None:
        family_transition_year = FAMILY_TRANSITION_YEAR

    # Extract program data
    raw_tuition = program.get("tuition_usd") or 0  # Total tuition in $K
    y1_salary = program.get("y1_salary_usd") or 0  # $K
    y5_salary = program.get("y5_salary_usd") or 0  # $K
    y10_salary = program.get("y10_salary_usd") or 0  # $K
    duration = program.get("duration_years") or DEFAULT_DURATION
    primary_market = program.get("primary_market") or ""
    uni_country = program.get("country") or "USA"

    # Apply financial aid based on scenario
    expected_aid = program.get("expected_aid_usd") or 0
    best_case_aid = program.get("best_case_aid_usd") or 0
    coop_earnings = program.get("coop_earnings_usd") or 0
    aid_type = program.get("aid_type") or "none"
    initial_capital_base = program.get("initial_capital_usd") or 0

    if aid_scenario == "expected":
        tuition = max(0, raw_tuition - expected_aid)
        scholarship_applied = expected_aid
    elif aid_scenario == "best_case":
        tuition = max(0, raw_tuition - best_case_aid)
        scholarship_applied = best_case_aid
    else:  # "no_aid" - default
        tuition = raw_tuition
        scholarship_applied = 0

    # Calculate adjusted initial capital based on aid scenario
    # Initial capital includes blocked account + first semester tuition + visa/flights
    # When scholarships cover tuition, the tuition portion of initial capital is reduced
    if aid_scenario == "no_aid":
        initial_capital = initial_capital_base
    elif aid_type == "guaranteed_funding":
        # Guaranteed funding (KAIST, MEXT, KAUST): minimal initial capital
        # Just need flights, visa, first month settling - typically $2-3K
        initial_capital = min(initial_capital_base, 3000)
    else:
        # Partial funding: reduce tuition component proportionally
        # Estimate tuition is ~40-50% of initial capital for most programs
        tuition_reduction_pct = min(1.0, scholarship_applied / max(raw_tuition, 1))
        # Assume tuition component is ~50% of initial capital (rest is living proof, visa, etc.)
        tuition_component = initial_capital_base * 0.5
        non_tuition_component = initial_capital_base * 0.5
        initial_capital = int(non_tuition_component + tuition_component * (1 - tuition_reduction_pct))

    # Get work location info
    market = get_market_info(primary_market, uni_country)
    work_country = market.work_country
    work_city = market.work_city
    us_state = market.us_state

    # Get study country for living costs during study years
    study_country = get_study_country_for_living_cost(uni_country)

    # ── Study period (calendar years 1-2) ────────────────────────────────
    study_years = int(duration)
    tuition_per_year = tuition / study_years if study_years > 0 else 0

    study_yearly = []
    total_study_cost = 0.0

    for cal_yr in range(1, study_years + 1):
        student_living = get_study_living_cost(
            study_country, "student", lifestyle=lifestyle
        )
        year_cost = tuition_per_year + student_living
        total_study_cost += year_cost

        study_yearly.append(
            {
                "calendar_year": cal_yr,
                "phase": "study",
                "tuition_k": round(tuition_per_year, 2),
                "living_cost_k": round(student_living, 2),
                "total_cost_k": round(year_cost, 2),
                "gross_salary_k": 0,
                "after_tax_k": 0,
                "annual_savings_k": round(-year_cost, 2),
            }
        )

    # ── Work period (calendar years 3-12, work years 1-10) ───────────────
    work_years = TOTAL_YEARS - study_years  # Should be 10
    work_yearly = []
    total_work_savings = 0.0

    for work_yr in range(1, work_years + 1):
        cal_yr = study_years + work_yr

        # Interpolate salary
        gross = interpolate_salary(y1_salary, y5_salary, y10_salary, work_yr)

        # Calculate after-tax income
        after_tax = calculate_annual_tax(gross, work_country, us_state, work_city)

        # Determine household type and living cost
        if cal_yr < family_transition_year:
            household = "single"
        else:
            household = "family"

        living_cost = get_annual_living_cost(
            work_city, household, work_country, lifestyle=lifestyle
        )

        # Annual savings
        annual_savings = after_tax - living_cost
        total_work_savings += annual_savings

        work_yearly.append(
            {
                "calendar_year": cal_yr,
                "work_year": work_yr,
                "phase": "work",
                "household": household,
                "gross_salary_k": round(gross, 2),
                "after_tax_k": round(after_tax, 2),
                "living_cost_k": round(living_cost, 2),
                "annual_savings_k": round(annual_savings, 2),
            }
        )

    # ── Net worth calculation ────────────────────────────────────────────
    # Add co-op earnings for co-op programs (reduces effective cost)
    if aid_scenario in ("expected", "best_case") and coop_earnings > 0:
        total_study_cost -= coop_earnings

    masters_networth = total_work_savings - total_study_cost

    # Cumulative tracking
    cumulative = 0.0
    all_yearly = []
    for entry in study_yearly + work_yearly:
        cumulative += entry["annual_savings_k"]
        entry["cumulative_k"] = round(cumulative, 2)
        all_yearly.append(entry)

    # Compare to baseline
    if baseline_total is None:
        baseline_total = float(
            calculate_baseline_networth(
                baseline_salary,
                baseline_growth,
                lifestyle=lifestyle,
                family_transition_year=family_transition_year,
            )["total_networth_k"]
        )

    net_benefit = masters_networth - baseline_total

    # Effective tax rate at Y1 and Y10
    eff_tax_y1 = (
        (
            1
            - (
                calculate_annual_tax(y1_salary, work_country, us_state, work_city)
                / y1_salary
            )
        )
        if y1_salary > 0
        else 0
    )
    eff_tax_y10 = (
        (
            1
            - (
                calculate_annual_tax(y10_salary, work_country, us_state, work_city)
                / y10_salary
            )
        )
        if y10_salary > 0
        else 0
    )

    return {
        "program_id": program.get("id"),
        "university": program.get("university_name") or program.get("university", ""),
        "program_name": program.get("program_name", ""),
        "country": uni_country,
        "field": program.get("field", ""),
        "funding_tier": program.get("funding_tier", ""),
        "duration_years": duration,
        # Location
        "work_country": work_country,
        "work_city": work_city,
        "us_state": us_state,
        "primary_market": primary_market,
        # Initial capital requirement (upfront funds needed before starting)
        "initial_capital_base_usd": initial_capital_base,  # No aid scenario
        "initial_capital_usd": initial_capital,  # Adjusted for aid scenario
        # Costs (raw vs effective)
        "raw_tuition_k": raw_tuition,
        "tuition_k": tuition,
        "study_living_cost_k": round(total_study_cost - tuition + (coop_earnings if aid_scenario in ("expected", "best_case") else 0), 2),
        "total_study_cost_k": round(total_study_cost, 2),
        # Financial Aid Info
        "aid_scenario": aid_scenario,
        "scholarship_applied_k": scholarship_applied,
        "coop_earnings_k": coop_earnings if aid_scenario in ("expected", "best_case") else 0,
        "aid_type": aid_type,
        "expected_aid_k": expected_aid,
        "best_case_aid_k": best_case_aid,
        # Earnings
        "total_work_savings_k": round(total_work_savings, 2),
        "masters_networth_k": round(masters_networth, 2),
        # Comparison
        "baseline_networth_k": round(baseline_total, 2),
        "net_benefit_k": round(net_benefit, 2),
        # Tax info
        "effective_tax_rate_y1": round(eff_tax_y1, 4),
        "effective_tax_rate_y10": round(eff_tax_y10, 4),
        # Salary trajectory
        "y1_salary_k": y1_salary,
        "y5_salary_k": y5_salary,
        "y10_salary_k": y10_salary,
        # Original DB value for comparison
        "db_net_10yr_k": program.get("net_10yr_usd"),
        # Yearly breakdown
        "yearly_breakdown": all_yearly,
    }


def calculate_all_programs(
    baseline_salary: Optional[float] = None,
    baseline_growth: Optional[float] = None,
    lifestyle: str = "frugal",
    family_transition_year: Optional[int] = None,
    aid_scenario: str = "no_aid",
):
    """
    Calculate net worth for all programs in the database.

    Args:
        baseline_salary: Override for baseline annual salary in $K USD.
        baseline_growth: Override for baseline annual growth rate.
        lifestyle: "frugal" or "comfortable" living cost tier.
        family_transition_year: Calendar year when household transitions to family
            (1-12, or 13 for never). Default: FAMILY_TRANSITION_YEAR (5).
        aid_scenario: Financial aid scenario:
            - "no_aid": Full sticker price (default)
            - "expected": Apply expected_aid_usd reduction
            - "best_case": Apply best_case_aid_usd reduction
    """
    if baseline_salary is None:
        baseline_salary = BASELINE_ANNUAL_SALARY_USD_K
    if baseline_growth is None:
        baseline_growth = BASELINE_ANNUAL_GROWTH
    if family_transition_year is None:
        family_transition_year = FAMILY_TRANSITION_YEAR

    with get_db() as conn:
        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                p.id, p.program_name, p.field, p.tuition_usd,
                p.y1_salary_usd, p.y5_salary_usd, p.y10_salary_usd,
                p.net_10yr_usd, p.funding_tier, p.duration_years,
                p.primary_market, p.notes,
                p.expected_aid_pct, p.expected_aid_usd,
                p.best_case_aid_pct, p.best_case_aid_usd,
                p.aid_type, p.coop_earnings_usd,
                p.initial_capital_usd,
                u.name as university_name, u.country, u.region
            FROM programs p
            JOIN universities u ON p.university_id = u.id
            ORDER BY p.net_10yr_usd DESC
        """)

        programs = [dict(row) for row in cursor.fetchall()]

    baseline = calculate_baseline_networth(
        baseline_salary,
        baseline_growth,
        lifestyle=lifestyle,
        family_transition_year=family_transition_year,
    )
    baseline_total = baseline["total_networth_k"]

    results = []
    for prog in programs:
        result = calculate_program_networth(
            prog,
            baseline_total,
            lifestyle=lifestyle,
            family_transition_year=family_transition_year,
            aid_scenario=aid_scenario,
        )
        results.append(result)

    # Sort by net benefit descending
    results.sort(key=lambda x: x["net_benefit_k"], reverse=True)

    # Compute summary statistics
    from collections import defaultdict

    tier_benefits = defaultdict(list)
    field_benefits = defaultdict(list)
    country_benefits = defaultdict(list)

    for r in results:
        tier_benefits[r["funding_tier"]].append(r["net_benefit_k"])
        field_benefits[r["field"]].append(r["net_benefit_k"])
        country_benefits[r["work_country"]].append(r["net_benefit_k"])

    positive = sum(1 for r in results if r["net_benefit_k"] > 0)

    return {
        "baseline": baseline,
        "assumptions": {
            "baseline_annual_salary_usd_k": baseline_salary,
            "baseline_annual_growth": baseline_growth,
            "total_years": TOTAL_YEARS,
            "study_years": int(DEFAULT_DURATION),
            "family_transition_year": family_transition_year,
            "tax_model": "progressive_brackets_per_country",
            "living_cost_model": "per_city_single_family_student",
            "lifestyle": lifestyle,
            "aid_scenario": aid_scenario,
        },
        "programs": results,
        "summary": {
            "total_programs": len(results),
            "programs_with_positive_benefit": positive,
            "top_5": [
                {
                    "university": r["university"],
                    "program": r["program_name"],
                    "net_benefit_k": r["net_benefit_k"],
                    "field": r["field"],
                    "work_country": r["work_country"],
                }
                for r in results[:5]
            ],
            "bottom_5": [
                {
                    "university": r["university"],
                    "program": r["program_name"],
                    "net_benefit_k": r["net_benefit_k"],
                    "field": r["field"],
                    "work_country": r["work_country"],
                }
                for r in results[-5:]
            ],
            "by_tier": avg_summary(tier_benefits),
            "by_field": avg_summary(field_benefits),
            "by_work_country": avg_summary(country_benefits),
        },
    }


def print_report():
    """Print a formatted report of all calculations."""
    data = calculate_all_programs()
    baseline = data["baseline"]
    programs = data["programs"]
    summary = data["summary"]

    print("=" * 110)
    print("  12-YEAR NET WORTH CALCULATOR V2 — MASTERS PROGRAMS")
    print("  Location-aware: progressive taxes + real living costs")
    print("=" * 110)

    print(f"\n  ASSUMPTIONS:")
    print(f"   Baseline salary: ${BASELINE_ANNUAL_SALARY_USD_K}K/yr (220K PKR/mo)")
    print(f"   Baseline growth: {BASELINE_ANNUAL_GROWTH * 100:.0f}%/yr")
    print(f"   Timeline:        {TOTAL_YEARS} years (2yr study + 10yr work)")
    print(f"   Household:       Single yrs 1-4, Family yrs 5-12")
    print(
        f"   Tax model:       Progressive brackets per country + social contributions"
    )
    print(f"   Living costs:    Per-city (student/single/family profiles)")

    print(
        f"\n  BASELINE (NO MASTERS) — 12yr Net Worth: ${baseline['total_networth_k']:.1f}K"
    )
    bl = baseline["yearly_breakdown"]
    print(
        f"   Year 1:  gross ${bl[0]['gross_salary_k']:.1f}K → after-tax ${bl[0]['after_tax_k']:.1f}K → saves ${bl[0]['annual_savings_k']:.1f}K"
    )
    print(
        f"   Year 12: gross ${bl[-1]['gross_salary_k']:.1f}K → after-tax ${bl[-1]['after_tax_k']:.1f}K → saves ${bl[-1]['annual_savings_k']:.1f}K"
    )

    print(f"\n{'=' * 110}")
    print(f"  TOP 30 PROGRAMS BY NET BENEFIT vs BASELINE")
    print(f"{'=' * 110}")
    header = f"{'#':>3} {'University':<22} {'Program':<18} {'Field':<8} {'Work Country':<14} {'StudyCst':>8} {'NetWorth':>9} {'Benefit':>9} {'EffTax%':>7}"
    print(header)
    print("-" * 110)

    for i, p in enumerate(programs[:30], 1):
        uni = p["university"][:21]
        prog = p["program_name"][:17]
        field = p["field"][:7]
        wc = p["work_country"][:13]
        study = f"${p['total_study_cost_k']:.0f}K"
        netw = f"${p['masters_networth_k']:.0f}K"
        benefit = (
            f"+${p['net_benefit_k']:.0f}K"
            if p["net_benefit_k"] > 0
            else f"-${abs(p['net_benefit_k']):.0f}K"
        )
        tax_pct = f"{p['effective_tax_rate_y10'] * 100:.0f}%"
        print(
            f"{i:>3} {uni:<22} {prog:<18} {field:<8} {wc:<14} {study:>8} {netw:>9} {benefit:>9} {tax_pct:>7}"
        )

    print(f"\n{'=' * 110}")
    print(f"  BOTTOM 10 PROGRAMS BY NET BENEFIT")
    print(f"{'=' * 110}")
    for i, p in enumerate(programs[-10:], len(programs) - 9):
        uni = p["university"][:21]
        prog = p["program_name"][:17]
        wc = p["work_country"][:13]
        benefit = (
            f"+${p['net_benefit_k']:.0f}K"
            if p["net_benefit_k"] > 0
            else f"-${abs(p['net_benefit_k']):.0f}K"
        )
        print(f"{i:>3} {uni:<22} {prog:<18} {p['field']:<8} {wc:<14} {benefit:>9}")

    print(f"\n{'=' * 110}")
    print(f"  AVERAGE NET BENEFIT BY FUNDING TIER")
    print(f"{'=' * 110}")
    for tier, stats in summary["by_tier"].items():
        print(
            f"   {tier:<28} avg: ${stats['avg']:>8.1f}K  (n={stats['count']:>3}, range: ${stats['min']:.0f}K to ${stats['max']:.0f}K)"
        )

    print(f"\n{'=' * 110}")
    print(f"  AVERAGE NET BENEFIT BY FIELD")
    print(f"{'=' * 110}")
    for field, stats in summary["by_field"].items():
        print(f"   {field:<20} avg: ${stats['avg']:>8.1f}K  (n={stats['count']:>3})")

    print(f"\n{'=' * 110}")
    print(f"  AVERAGE NET BENEFIT BY WORK COUNTRY (top 15)")
    print(f"{'=' * 110}")
    for i, (country, stats) in enumerate(summary["by_work_country"].items()):
        if i >= 15:
            break
        print(f"   {country:<20} avg: ${stats['avg']:>8.1f}K  (n={stats['count']:>3})")

    print(f"\n  SUMMARY:")
    print(
        f"   {summary['programs_with_positive_benefit']}/{summary['total_programs']} programs have positive net benefit vs staying in Pakistan"
    )
    pct = summary["programs_with_positive_benefit"] / summary["total_programs"] * 100
    print(
        f"   ({pct:.0f}% of programs are financially worth it over {TOTAL_YEARS} years)"
    )


if __name__ == "__main__":
    print_report()
