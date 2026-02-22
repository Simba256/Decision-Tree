"""
Shared Calculation Utilities for Net Worth Calculators
======================================================
Common functions used by both the masters program calculator
(networth_calculator.py) and the career path calculator
(career_networth_calculator.py).
"""

from typing import Optional

from config import BASELINE_ANNUAL_SALARY_USD_K, BASELINE_ANNUAL_GROWTH
from tax_data import calculate_annual_tax
from living_costs import get_pakistan_living_cost


def interpolate_salary(y1: float, y5: float, y10: float, work_year: int) -> float:
    """
    Linearly interpolate salary for a given work year (1-indexed, post-graduation).
    Y1, Y5, Y10 are salary data points in $K USD for work experience years.
    """
    if work_year <= 1:
        return y1
    elif work_year <= 5:
        t = (work_year - 1) / (5 - 1)
        return y1 + t * (y5 - y1)
    elif work_year <= 10:
        t = (work_year - 5) / (10 - 5)
        return y5 + t * (y10 - y5)
    else:
        return y10


def avg_summary(groups: dict) -> dict:
    """
    Compute average/min/max/count summary for grouped numeric lists.

    Args:
        groups: Dict mapping group name to list of numeric values.

    Returns:
        Dict of {group_name: {avg, count, min, max}}, sorted by avg descending.
    """
    return {
        k: {
            "avg": round(sum(v) / len(v), 1) if v else 0,
            "count": len(v),
            "min": round(min(v), 1) if v else 0,
            "max": round(max(v), 1) if v else 0,
        }
        for k, v in sorted(
            groups.items(),
            key=lambda x: sum(x[1]) / len(x[1]) if x[1] else 0,
            reverse=True,
        )
    }


def calculate_pakistan_baseline(
    total_years: int,
    default_family_year: int,
    year_key: str = "year",
    baseline_salary: Optional[float] = None,
    baseline_growth: Optional[float] = None,
    lifestyle: str = "frugal",
    family_transition_year: Optional[int] = None,
) -> dict:
    """
    Calculate cumulative net worth on the no-change baseline path
    (staying in Pakistan with current salary + annual growth).
    Single living until family_transition_year, then family living.

    This is the unified implementation used by both the masters calculator
    (12yr, family_year=5, year_key="calendar_year") and the career calculator
    (10yr, family_year=3, year_key="year").

    Args:
        total_years: Number of years for the projection (12 for masters, 10 for career).
        default_family_year: Default calendar year for single→family transition.
        year_key: Key name for the year field in yearly breakdown dicts
            ("calendar_year" for masters, "year" for career).
        baseline_salary: Override for baseline annual salary in $K USD.
        baseline_growth: Override for baseline annual growth rate.
        lifestyle: "frugal" or "comfortable" living cost tier.
        family_transition_year: Calendar year when household transitions to family.
            Defaults to default_family_year if not provided.

    Returns:
        Dict with total_networth_k and yearly_breakdown.
    """
    if baseline_salary is None:
        baseline_salary = BASELINE_ANNUAL_SALARY_USD_K
    if baseline_growth is None:
        baseline_growth = BASELINE_ANNUAL_GROWTH
    if family_transition_year is None:
        family_transition_year = default_family_year

    yearly = []
    total = 0.0
    salary = baseline_salary

    for yr in range(1, total_years + 1):
        household = "single" if yr < family_transition_year else "family"

        # Pakistan taxes
        after_tax = calculate_annual_tax(salary, "Pakistan")

        # Pakistan living costs
        living_cost = get_pakistan_living_cost(household, lifestyle=lifestyle)

        annual_savings = after_tax - living_cost
        total += annual_savings

        yearly.append(
            {
                year_key: yr,
                "gross_salary_k": round(salary, 2),
                "after_tax_k": round(after_tax, 2),
                "living_cost_k": round(living_cost, 2),
                "household": household,
                "annual_savings_k": round(annual_savings, 2),
                "cumulative_k": round(total, 2),
            }
        )

        salary *= 1 + baseline_growth

    return {
        "total_networth_k": round(total, 2),
        "yearly_breakdown": yearly,
    }
