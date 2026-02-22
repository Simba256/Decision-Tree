"""
Net Worth Calculator for Career / Trading / Startup / Freelance Paths
=====================================================================
10-year net worth calculator for non-masters career paths.

Unlike the masters calculator, these paths:
  - Have NO study period (all 10 years are working years)
  - Are ALWAYS based in Pakistan (Pakistan taxes, Pakistan living costs)
  - May have initial capital requirements (trading, startup, freelance setup)
  - May have ongoing monthly costs (platform fees, hosting, tools)
  - Use income fields (y1/y5/y10_income_usd) instead of salary fields

Timeline: 10 calendar years (work years 1-10)
  - Household: single until family_transition_year (default 3), then family
    (Earlier than masters because there's no 2-year study gap)

Net Worth Formula:
  path_networth = Σ(yr 1-10)[after_tax_income - pakistan_living_cost - ongoing_costs]
                  - initial_capital
  baseline_networth = Σ(yr 1-10)[after_tax_baseline_salary - pakistan_living_cost]
  net_benefit = path_networth - baseline_networth

All values in $K USD unless otherwise noted.
"""

import sqlite3
from typing import Optional

from config import DB_PATH, get_db, BASELINE_ANNUAL_SALARY_USD_K, BASELINE_ANNUAL_GROWTH
from calculator_common import (
    interpolate_salary,
    avg_summary,
    calculate_pakistan_baseline,
)
from tax_data import calculate_annual_tax
from living_costs import get_pakistan_living_cost

# ─── Configuration ───────────────────────────────────────────────────────────

# Calendar year when household transitions from single to family
# Year 3 for career paths (no 2-year study gap, so family transition earlier)
FAMILY_TRANSITION_YEAR = 3

# Total years for career path projection
TOTAL_YEARS = 10


# ─── Core Calculation Functions ──────────────────────────────────────────────


def calculate_career_baseline(
    baseline_salary: Optional[float] = None,
    baseline_growth: Optional[float] = None,
    lifestyle: str = "frugal",
    family_transition_year: Optional[int] = None,
) -> dict:
    """
    Calculate 10-year cumulative net worth on the baseline path
    (staying in current role in Pakistan with annual growth).

    Args:
        baseline_salary: Override for baseline annual salary in $K USD.
        baseline_growth: Override for baseline annual growth rate.
        lifestyle: "frugal" or "comfortable" living cost tier.
        family_transition_year: Calendar year when household transitions to family
            (1-10, or 11 for never). Default: FAMILY_TRANSITION_YEAR (3).

    Returns:
        Dict with total_networth_k and yearly_breakdown.
    """
    return calculate_pakistan_baseline(
        total_years=TOTAL_YEARS,
        default_family_year=FAMILY_TRANSITION_YEAR,
        year_key="year",
        baseline_salary=baseline_salary,
        baseline_growth=baseline_growth,
        lifestyle=lifestyle,
        family_transition_year=family_transition_year,
    )


def calculate_career_node_networth(
    node: dict,
    baseline_total: Optional[float] = None,
    baseline_salary: Optional[float] = None,
    baseline_growth: Optional[float] = None,
    lifestyle: str = "frugal",
    family_transition_year: Optional[int] = None,
) -> dict:
    """
    Calculate 10-year net worth for a specific career node.

    Timeline:
      Years 1-10: Working in Pakistan.
      Household transitions from single to family at family_transition_year.
      Initial capital deducted at year 0, ongoing costs deducted each year.

    Args:
        node: Dict with career node data (from career_nodes table).
        baseline_total: Pre-calculated baseline net worth in $K USD.
            If None, calculates it internally.
        baseline_salary: Override for baseline annual salary in $K USD.
        baseline_growth: Override for baseline annual growth rate.
        lifestyle: "frugal" or "comfortable" living cost tier.
        family_transition_year: Calendar year when household transitions to family
            (1-10, or 11 for never). Default: FAMILY_TRANSITION_YEAR (3).

    Returns:
        Dict with net worth breakdown, comparison to baseline, and yearly details.
    """
    if family_transition_year is None:
        family_transition_year = FAMILY_TRANSITION_YEAR

    # ── Extract node financial data ──────────────────────────────────────
    # y1/y5/y10_income_usd are annual income in $K USD
    y1_income = node.get("y1_income_usd") or 0
    y5_income = node.get("y5_income_usd") or 0
    y10_income = node.get("y10_income_usd") or 0

    # initial_capital_usd is a one-time cost in full USD (not thousands)
    initial_capital = (node.get("initial_capital_usd") or 0) / 1000  # Convert to $K

    # ongoing_cost_usd is monthly cost in full USD → convert to annual $K
    ongoing_monthly = node.get("ongoing_cost_usd") or 0
    ongoing_annual_k = (ongoing_monthly * 12) / 1000  # Convert to $K

    # ── Work period (years 1-10) ─────────────────────────────────────────
    yearly = []
    total_work_savings = 0.0

    for work_yr in range(1, TOTAL_YEARS + 1):
        # Interpolate income for this year
        gross = interpolate_salary(y1_income, y5_income, y10_income, work_yr)

        # Pakistan taxes on this income
        after_tax = calculate_annual_tax(gross, "Pakistan")

        # Household type and living cost
        household = "single" if work_yr < family_transition_year else "family"
        living_cost = get_pakistan_living_cost(household, lifestyle=lifestyle)

        # Annual savings = after-tax income - living costs - ongoing costs
        annual_savings = after_tax - living_cost - ongoing_annual_k
        total_work_savings += annual_savings

        yearly.append(
            {
                "year": work_yr,
                "gross_income_k": round(gross, 2),
                "after_tax_k": round(after_tax, 2),
                "living_cost_k": round(living_cost, 2),
                "ongoing_cost_k": round(ongoing_annual_k, 2),
                "household": household,
                "annual_savings_k": round(annual_savings, 2),
            }
        )

    # ── Net worth calculation ────────────────────────────────────────────
    path_networth = total_work_savings - initial_capital

    # Cumulative tracking (including initial capital deduction at year 0)
    cumulative = -initial_capital
    for entry in yearly:
        cumulative += entry["annual_savings_k"]
        entry["cumulative_k"] = round(cumulative, 2)

    # ── Compare to baseline ──────────────────────────────────────────────
    if baseline_total is None:
        baseline_total = float(
            calculate_career_baseline(
                baseline_salary,
                baseline_growth,
                lifestyle=lifestyle,
                family_transition_year=family_transition_year,
            )["total_networth_k"]
        )

    net_benefit = path_networth - baseline_total

    # Effective tax rate at Y1 and Y10
    eff_tax_y1 = (
        (1 - (calculate_annual_tax(y1_income, "Pakistan") / y1_income))
        if y1_income > 0
        else 0
    )
    eff_tax_y10 = (
        (1 - (calculate_annual_tax(y10_income, "Pakistan") / y10_income))
        if y10_income > 0
        else 0
    )

    return {
        "node_id": node.get("id"),
        "label": node.get("label", ""),
        "node_type": node.get("node_type", ""),
        "phase": node.get("phase"),
        "note": node.get("note", ""),
        # Income trajectory
        "y1_income_k": y1_income,
        "y5_income_k": y5_income,
        "y10_income_k": y10_income,
        # Costs
        "initial_capital_k": round(initial_capital, 2),
        "ongoing_annual_k": round(ongoing_annual_k, 2),
        "income_floor_usd": node.get("income_floor_usd"),
        "income_ceiling_usd": node.get("income_ceiling_usd"),
        # Net worth
        "total_work_savings_k": round(total_work_savings, 2),
        "path_networth_k": round(path_networth, 2),
        # Comparison
        "baseline_networth_k": round(baseline_total, 2),
        "net_benefit_k": round(net_benefit, 2),
        # Tax info
        "effective_tax_rate_y1": round(eff_tax_y1, 4),
        "effective_tax_rate_y10": round(eff_tax_y10, 4),
        # Yearly breakdown
        "yearly_breakdown": yearly,
    }


def calculate_all_career_paths(
    node_type: Optional[str] = None,
    leaf_only: bool = True,
    baseline_salary: Optional[float] = None,
    baseline_growth: Optional[float] = None,
    lifestyle: str = "frugal",
    family_transition_year: Optional[int] = None,
) -> dict:
    """
    Calculate net worth for all career path nodes (or filtered subset).

    Args:
        node_type: Filter by node_type ("career", "trading", "startup", "freelance").
            None = all non-masters paths.
        leaf_only: If True (default), only calculate for leaf nodes (nodes with
            no children in the edges table). Leaf nodes represent final outcomes.
        baseline_salary: Override for baseline annual salary in $K USD.
        baseline_growth: Override for baseline annual growth rate.
        lifestyle: "frugal" or "comfortable" living cost tier.
        family_transition_year: Calendar year for single→family transition.

    Returns:
        Dict with baseline, assumptions, results list, and summary statistics.
    """
    if baseline_salary is None:
        baseline_salary = BASELINE_ANNUAL_SALARY_USD_K
    if baseline_growth is None:
        baseline_growth = BASELINE_ANNUAL_GROWTH
    if family_transition_year is None:
        family_transition_year = FAMILY_TRANSITION_YEAR

    with get_db() as conn:
        cursor = conn.cursor()

        # Get all career nodes (non-masters)
        query = "SELECT * FROM career_nodes WHERE 1=1"
        params = []

        if node_type:
            query += " AND node_type = ?"
            params.append(node_type)

        query += " ORDER BY node_type, phase, id"
        cursor.execute(query, params)
        all_nodes = [dict(row) for row in cursor.fetchall()]

        # If leaf_only, find nodes that are NOT parents in any child edge
        if leaf_only:
            cursor.execute(
                "SELECT DISTINCT source_id FROM edges WHERE link_type = 'child'"
            )
            parent_ids = {row["source_id"] for row in cursor.fetchall()}
            nodes = [n for n in all_nodes if n["id"] not in parent_ids]
        else:
            nodes = all_nodes

        # Load edge probabilities for probability-weighted expected value
        cursor.execute(
            "SELECT source_id, target_id, probability FROM edges WHERE link_type = 'child'"
        )
        edge_probs = {}
        for row in cursor.fetchall():
            edge_probs[(row["source_id"], row["target_id"])] = row["probability"]

    # Calculate baseline once
    baseline = calculate_career_baseline(
        baseline_salary,
        baseline_growth,
        lifestyle=lifestyle,
        family_transition_year=family_transition_year,
    )
    baseline_total = baseline["total_networth_k"]

    # Calculate net worth for each node
    results = []
    for node in nodes:
        # Skip nodes with no income data
        if not node.get("y1_income_usd") and not node.get("y10_income_usd"):
            continue

        result = calculate_career_node_networth(
            node,
            baseline_total,
            lifestyle=lifestyle,
            family_transition_year=family_transition_year,
        )

        # Add probability info: find this node's cumulative path probability
        # by tracing edges from root. For now, store the node's own edge prob
        # from its parents (there may be multiple parents for shared nodes).
        node_id = node["id"]
        parent_probs = [
            (src, prob) for (src, tgt), prob in edge_probs.items() if tgt == node_id
        ]
        result["parent_edges"] = [
            {"parent_id": src, "probability": prob} for src, prob in parent_probs
        ]

        results.append(result)

    # Sort by net benefit descending
    results.sort(key=lambda x: x["net_benefit_k"], reverse=True)

    # ── Summary statistics ───────────────────────────────────────────────
    from collections import defaultdict

    type_benefits = defaultdict(list)
    phase_benefits = defaultdict(list)

    for r in results:
        type_benefits[r["node_type"]].append(r["net_benefit_k"])
        phase_benefits[r.get("phase") or "unknown"].append(r["net_benefit_k"])

    positive = sum(1 for r in results if r["net_benefit_k"] > 0)

    return {
        "baseline": baseline,
        "assumptions": {
            "baseline_annual_salary_usd_k": baseline_salary,
            "baseline_annual_growth": baseline_growth,
            "total_years": TOTAL_YEARS,
            "family_transition_year": family_transition_year,
            "tax_jurisdiction": "Pakistan",
            "living_cost_location": "Pakistan",
            "lifestyle": lifestyle,
            "leaf_only": leaf_only,
            "node_type_filter": node_type,
        },
        "results": results,
        "summary": {
            "total_nodes": len(results),
            "nodes_with_positive_benefit": positive,
            "top_5": [
                {
                    "node_id": r["node_id"],
                    "label": r["label"],
                    "node_type": r["node_type"],
                    "net_benefit_k": r["net_benefit_k"],
                    "y10_income_k": r["y10_income_k"],
                }
                for r in results[:5]
            ],
            "bottom_5": [
                {
                    "node_id": r["node_id"],
                    "label": r["label"],
                    "node_type": r["node_type"],
                    "net_benefit_k": r["net_benefit_k"],
                    "y10_income_k": r["y10_income_k"],
                }
                for r in results[-5:]
            ],
            "by_type": avg_summary(type_benefits),
            "by_phase": avg_summary(phase_benefits),
        },
    }


# ─── CLI Report ──────────────────────────────────────────────────────────────


def print_report():
    """Print a formatted report of all career path net worth calculations."""
    data = calculate_all_career_paths()
    baseline = data["baseline"]
    results = data["results"]
    summary = data["summary"]

    print("=" * 120)
    print(
        "  10-YEAR NET WORTH CALCULATOR — CAREER / TRADING / STARTUP / FREELANCE PATHS"
    )
    print(
        "  Location: Pakistan | Taxes: Pakistan progressive brackets | Living: Pakistan costs"
    )
    print("=" * 120)

    print(f"\n  ASSUMPTIONS:")
    print(f"   Baseline salary: ${BASELINE_ANNUAL_SALARY_USD_K}K/yr (220K PKR/mo)")
    print(f"   Baseline growth: {BASELINE_ANNUAL_GROWTH * 100:.0f}%/yr")
    print(f"   Timeline:        {TOTAL_YEARS} years (all working)")
    print(
        f"   Household:       Single yrs 1-{FAMILY_TRANSITION_YEAR - 1}, Family yrs {FAMILY_TRANSITION_YEAR}-{TOTAL_YEARS}"
    )
    print(f"   Tax model:       Pakistan progressive brackets")
    print(f"   Living costs:    Pakistan (single/family profiles)")

    print(
        f"\n  BASELINE (STAY IN CURRENT ROLE) — 10yr Net Worth: ${baseline['total_networth_k']:.1f}K"
    )
    bl = baseline["yearly_breakdown"]
    print(
        f"   Year 1:  gross ${bl[0]['gross_salary_k']:.1f}K → after-tax ${bl[0]['after_tax_k']:.1f}K → saves ${bl[0]['annual_savings_k']:.1f}K"
    )
    print(
        f"   Year 10: gross ${bl[-1]['gross_salary_k']:.1f}K → after-tax ${bl[-1]['after_tax_k']:.1f}K → saves ${bl[-1]['annual_savings_k']:.1f}K"
    )

    print(f"\n{'=' * 120}")
    print(f"  ALL CAREER PATHS BY NET BENEFIT vs BASELINE (leaf nodes only)")
    print(f"{'=' * 120}")
    header = f"{'#':>3} {'Type':<10} {'Label':<40} {'Y1':>7} {'Y10':>7} {'Capital':>8} {'NetWorth':>9} {'Benefit':>9}"
    print(header)
    print("-" * 120)

    for i, r in enumerate(results, 1):
        # Clean label: replace newlines with spaces, strip emoji
        label = (r["label"] or r["node_id"]).replace("\\n", " ").replace("\n", " ")[:39]
        ntype = r["node_type"][:9]
        y1 = f"${r['y1_income_k']:.0f}K"
        y10 = f"${r['y10_income_k']:.0f}K"
        cap = f"${r['initial_capital_k']:.1f}K" if r["initial_capital_k"] > 0 else "-"
        netw = f"${r['path_networth_k']:.0f}K"
        benefit = (
            f"+${r['net_benefit_k']:.0f}K"
            if r["net_benefit_k"] > 0
            else f"-${abs(r['net_benefit_k']):.0f}K"
        )
        print(
            f"{i:>3} {ntype:<10} {label:<40} {y1:>7} {y10:>7} {cap:>8} {netw:>9} {benefit:>9}"
        )

    print(f"\n{'=' * 120}")
    print(f"  AVERAGE NET BENEFIT BY TYPE")
    print(f"{'=' * 120}")
    for ntype, stats in summary["by_type"].items():
        print(
            f"   {ntype:<20} avg: ${stats['avg']:>8.1f}K  (n={stats['count']:>3}, range: ${stats['min']:.0f}K to ${stats['max']:.0f}K)"
        )

    print(f"\n  SUMMARY:")
    print(
        f"   {summary['nodes_with_positive_benefit']}/{summary['total_nodes']} career paths have positive net benefit vs staying in current role"
    )
    if summary["total_nodes"] > 0:
        pct = summary["nodes_with_positive_benefit"] / summary["total_nodes"] * 100
        print(
            f"   ({pct:.0f}% of paths are financially worth it over {TOTAL_YEARS} years)"
        )


if __name__ == "__main__":
    print_report()
