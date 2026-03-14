"""
Post-Masters Career Path Net Worth Calculator
==============================================

Calculates 12-year net worth for specific post-masters career paths.

Timeline:
  - Years 1-2: Study period (tuition + student living costs)
  - Years 3-12: Post-masters career path (work years 1-10)

This calculator extends networth_calculator.py by modeling career branching
after graduation, with location-dependent probabilities and outcomes.
"""

import json
import sqlite3
from collections import defaultdict
from dataclasses import dataclass
from typing import Optional

from config import (
    DB_PATH,
    get_db,
    MASTERS_TOTAL_YEARS,
    MASTERS_DEFAULT_FAMILY_YEAR,
    MASTERS_DEFAULT_DURATION,
)
from calculator_common import interpolate_salary, calculate_pakistan_baseline
from market_mapping import get_market_info, get_study_country_for_living_cost
from tax_data import calculate_annual_tax
from living_costs import (
    get_annual_living_cost,
    get_study_living_cost,
    get_pakistan_living_cost,
)
from location_ecosystem import (
    get_ecosystem,
    get_ecosystem_by_country,
    LocationEcosystem,
    calculate_startup_success_modifier,
    calculate_bigtech_modifier,
)

# ─── Configuration ───────────────────────────────────────────────────────────

TOTAL_YEARS = MASTERS_TOTAL_YEARS  # 12 years
FAMILY_TRANSITION_YEAR = MASTERS_DEFAULT_FAMILY_YEAR  # Default year 5
DEFAULT_DURATION = MASTERS_DEFAULT_DURATION  # 2 years


@dataclass
class PostmastersNode:
    """Post-masters node data."""

    id: str
    phase: int
    node_type: str
    label: str
    salary_multiplier: float = 1.0
    equity_expected_value_usd: int = 0
    base_probability: float = 0.0
    requires_location_type: Optional[str] = None
    living_cost_location: Optional[str] = None
    tax_country: Optional[str] = None
    color: Optional[str] = None
    note: Optional[str] = None
    children: list = None


def get_postmasters_nodes() -> dict[str, PostmastersNode]:
    """Load all post-masters nodes from database."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM postmasters_nodes")
        rows = cursor.fetchall()

    nodes = {}
    for row in rows:
        children = json.loads(row["children"] or "[]")
        nodes[row["id"]] = PostmastersNode(
            id=row["id"],
            phase=row["phase"],
            node_type=row["node_type"],
            label=row["label"],
            salary_multiplier=row["salary_multiplier"] or 1.0,
            equity_expected_value_usd=row["equity_expected_value_usd"] or 0,
            base_probability=row["base_probability"] or 0.0,
            requires_location_type=row["requires_location_type"],
            living_cost_location=row["living_cost_location"],
            tax_country=row["tax_country"],
            color=row["color"],
            note=row["note"],
            children=children,
        )
    return nodes


def get_postmasters_edges() -> list[dict]:
    """Load all post-masters edges from database."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM postmasters_edges")
        rows = cursor.fetchall()
    return [dict(row) for row in rows]


def get_edges_by_source() -> dict[str, list[dict]]:
    """Get edges grouped by source node ID."""
    edges = get_postmasters_edges()
    by_source = defaultdict(list)
    for edge in edges:
        by_source[edge["source_id"]].append(edge)
    return dict(by_source)


def calibrate_edge_probability(
    edge: dict,
    ecosystem: LocationEcosystem,
) -> float:
    """
    Apply location-based calibration to edge probability.

    Adjusts base probability using ecosystem weights:
      adjusted_P = base_P * (1 + startup_weight * (ecosystem_strength - 1.0)
                            + bigtech_weight * (bigtech_modifier - 1.0))
    """
    base_p = edge["base_probability"]

    # Get startup ecosystem modifier (strength - 1.0 gives the delta)
    startup_weight = edge.get("startup_ecosystem_weight") or 0.0
    startup_delta = ecosystem.startup_ecosystem_strength - 1.0
    startup_adjustment = startup_weight * startup_delta

    # Get bigtech modifier
    bigtech_weight = edge.get("bigtech_presence_weight") or 0.0
    bigtech_modifier = calculate_bigtech_modifier(ecosystem)
    bigtech_delta = bigtech_modifier - 1.0
    bigtech_adjustment = bigtech_weight * bigtech_delta

    # Apply adjustments
    total_adjustment = 1.0 + startup_adjustment + bigtech_adjustment

    # Clamp to reasonable range
    adjusted_p = base_p * max(0.5, min(2.0, total_adjustment))

    return adjusted_p


def calibrate_and_normalize_edges(
    edges_by_source: dict[str, list[dict]],
    ecosystem: LocationEcosystem,
) -> dict[str, dict[str, float]]:
    """
    Calibrate all edges and normalize child groups to sum to 1.0.

    Returns:
        Nested dict: edge_map[source_id][target_id] = calibrated_probability
    """
    edge_map = {}

    for source_id, edges in edges_by_source.items():
        # Calibrate each edge
        calibrated = []
        for edge in edges:
            cal_p = calibrate_edge_probability(edge, ecosystem)
            calibrated.append((edge["target_id"], cal_p))

        # Normalize to sum to 1.0
        total = sum(p for _, p in calibrated)
        if total > 0:
            edge_map[source_id] = {
                target_id: round(p / total, 4) for target_id, p in calibrated
            }
        else:
            # Fallback: equal distribution
            n = len(calibrated)
            edge_map[source_id] = {
                target_id: round(1.0 / n, 4) for target_id, _ in calibrated
            }

    return edge_map


def get_node_for_work_year(
    path: list[str],
    work_year: int,
    nodes: dict[str, PostmastersNode],
) -> PostmastersNode:
    """
    Determine which node applies to a specific work year (1-10).

    Path phases map to work years roughly:
      - Phase 0: Year 1 (post-graduation decision)
      - Phase 1: Years 2-4 (career development)
      - Phase 2: Years 5-8 (senior/founding)
      - Phase 3: Years 9-10 (terminal)
    """
    # Map work year to approximate phase
    if work_year <= 1:
        target_phase = 0
    elif work_year <= 4:
        target_phase = 1
    elif work_year <= 8:
        target_phase = 2
    else:
        target_phase = 3

    # Find the node in path closest to target phase
    best_node = None
    best_distance = float("inf")

    for node_id in path:
        if node_id not in nodes:
            continue
        node = nodes[node_id]
        distance = abs(node.phase - target_phase)
        if distance < best_distance:
            best_distance = distance
            best_node = node

    # If no node found, return the last node in path
    if best_node is None and path:
        best_node = nodes.get(path[-1])

    return best_node


def calculate_path_income(
    program: dict,
    node: PostmastersNode,
    work_year: int,
    ecosystem: LocationEcosystem,
) -> tuple[float, str, str]:
    """
    Calculate gross income for a path node at a specific work year.

    Returns:
        Tuple of (gross_income_k, tax_country, work_city)
    """
    # Base salary from program (Y1, Y5, Y10)
    y1_salary = program.get("y1_salary_usd") or 0
    y5_salary = program.get("y5_salary_usd") or 0
    y10_salary = program.get("y10_salary_usd") or 0

    # Interpolate base salary for this year
    base_salary = interpolate_salary(y1_salary, y5_salary, y10_salary, work_year)

    # Apply node's salary multiplier
    gross = base_salary * node.salary_multiplier

    # Add expected equity value (spread over 4 years)
    if node.equity_expected_value_usd > 0 and work_year >= 4:
        equity_annual = node.equity_expected_value_usd / 4000  # Convert to $K
        gross += equity_annual

    # Determine tax country and work city
    if node.tax_country:
        tax_country = node.tax_country
    else:
        primary_market = program.get("primary_market") or ""
        uni_country = program.get("country") or "USA"
        market = get_market_info(primary_market, uni_country)
        tax_country = market.work_country

    # Determine work city for living costs
    if node.living_cost_location == "Pakistan":
        work_city = "Lahore"  # Default Pakistan city
    elif node.living_cost_location == "chosen":
        # Remote arbitrage - use a mid-cost city as proxy
        work_city = ecosystem.city
    else:
        primary_market = program.get("primary_market") or ""
        uni_country = program.get("country") or "USA"
        market = get_market_info(primary_market, uni_country)
        work_city = market.work_city

    return gross, tax_country, work_city


def calculate_postmasters_path_networth(
    program: dict,
    path: list[str],
    ecosystem: Optional[LocationEcosystem] = None,
    lifestyle: str = "frugal",
    family_year: int = FAMILY_TRANSITION_YEAR,
    aid_scenario: str = "no_aid",
) -> dict:
    """
    Calculate 12-year net worth for a specific post-masters career path.

    Args:
        program: Program dict with salary and tuition data
        path: List of node IDs representing the career path
            e.g., ["pm_bigtech", "pm_bigtech_senior", "pm_bigtech_staff"]
        ecosystem: Location ecosystem for the work city. If None, inferred from program.
        lifestyle: "frugal" or "comfortable" living cost tier
        family_year: Calendar year for single→family transition (1-12)
        aid_scenario: Financial aid scenario ("no_aid", "expected", "best_case")

    Returns:
        Dict with path_net_worth_k, path details, and yearly breakdown
    """
    nodes = get_postmasters_nodes()

    # Infer ecosystem from program if not provided
    if ecosystem is None:
        primary_market = program.get("primary_market") or ""
        uni_country = program.get("country") or "USA"
        market = get_market_info(primary_market, uni_country)
        ecosystem = get_ecosystem(market.work_city, market.work_country)
        if ecosystem is None:
            ecosystem = get_ecosystem_by_country(market.work_country)

    # ── Study Period (Years 1-2) ────────────────────────────────────────────
    raw_tuition = program.get("tuition_usd") or 0
    duration = program.get("duration_years") or DEFAULT_DURATION
    uni_country = program.get("country") or "USA"

    # Apply financial aid
    expected_aid = program.get("expected_aid_usd") or 0
    best_case_aid = program.get("best_case_aid_usd") or 0
    coop_earnings = program.get("coop_earnings_usd") or 0

    if aid_scenario == "expected":
        tuition = max(0, raw_tuition - expected_aid)
    elif aid_scenario == "best_case":
        tuition = max(0, raw_tuition - best_case_aid)
    else:
        tuition = raw_tuition

    study_country = get_study_country_for_living_cost(uni_country)
    study_years = int(duration)
    tuition_per_year = tuition / duration if duration > 0 else 0

    total_study_cost = 0.0
    study_yearly = []

    for cal_yr in range(1, study_years + 1):
        student_living = get_study_living_cost(
            study_country, "student", lifestyle=lifestyle
        )
        year_cost = tuition_per_year + student_living
        total_study_cost += year_cost

        study_yearly.append({
            "calendar_year": cal_yr,
            "phase": "study",
            "tuition_k": round(tuition_per_year, 2),
            "living_cost_k": round(student_living, 2),
            "total_cost_k": round(year_cost, 2),
            "gross_salary_k": 0,
            "after_tax_k": 0,
            "annual_savings_k": round(-year_cost, 2),
        })

    # Apply co-op earnings if applicable
    if aid_scenario in ("expected", "best_case") and coop_earnings > 0:
        effective_coop = min(coop_earnings, total_study_cost)
        total_study_cost -= effective_coop

    # ── Work Period (Years 3-12, Work Years 1-10) ───────────────────────────
    work_years = TOTAL_YEARS - study_years
    work_yearly = []
    total_work_savings = 0.0

    for work_yr in range(1, work_years + 1):
        cal_yr = study_years + work_yr

        # Get node for this work year
        node = get_node_for_work_year(path, work_yr, nodes)
        if node is None:
            continue

        # Calculate income
        gross, tax_country, work_city = calculate_path_income(
            program, node, work_yr, ecosystem
        )

        # Calculate after-tax
        if tax_country == "Pakistan":
            after_tax = calculate_annual_tax(gross, "Pakistan")
        else:
            primary_market = program.get("primary_market") or ""
            market = get_market_info(primary_market, program.get("country") or "USA")
            after_tax = calculate_annual_tax(
                gross, tax_country, market.us_state, work_city
            )

        # Determine household and living cost
        household = "single" if cal_yr < family_year else "family"

        if node.living_cost_location == "Pakistan":
            living_cost = get_pakistan_living_cost(household, lifestyle=lifestyle)
        else:
            living_cost = get_annual_living_cost(
                work_city, household, tax_country, lifestyle=lifestyle
            )

        annual_savings = after_tax - living_cost
        total_work_savings += annual_savings

        work_yearly.append({
            "calendar_year": cal_yr,
            "work_year": work_yr,
            "phase": "work",
            "node_id": node.id,
            "node_type": node.node_type,
            "household": household,
            "gross_salary_k": round(gross, 2),
            "after_tax_k": round(after_tax, 2),
            "living_cost_k": round(living_cost, 2),
            "annual_savings_k": round(annual_savings, 2),
            "tax_country": tax_country,
            "work_city": work_city,
        })

    # ── Net Worth Calculation ───────────────────────────────────────────────
    path_networth = total_work_savings - total_study_cost

    # Cumulative tracking
    cumulative = 0.0
    all_yearly = []
    for entry in study_yearly + work_yearly:
        cumulative += entry["annual_savings_k"]
        entry["cumulative_k"] = round(cumulative, 2)
        all_yearly.append(entry)

    # Get path node details
    path_nodes = [nodes.get(node_id) for node_id in path if node_id in nodes]

    return {
        "path": path,
        "path_description": " → ".join(
            n.label.replace("\\n", " ") for n in path_nodes if n
        ),
        "path_net_worth_k": round(path_networth, 2),
        "total_study_cost_k": round(total_study_cost, 2),
        "total_work_savings_k": round(total_work_savings, 2),
        "ecosystem_city": ecosystem.city if ecosystem else None,
        "ecosystem_strength": ecosystem.startup_ecosystem_strength if ecosystem else 1.0,
        "yearly_breakdown": all_yearly,
        "nodes": [
            {
                "id": n.id,
                "label": n.label,
                "phase": n.phase,
                "node_type": n.node_type,
                "salary_multiplier": n.salary_multiplier,
            }
            for n in path_nodes
            if n
        ],
    }


def calculate_path_probability(
    path: list[str],
    edge_map: dict[str, dict[str, float]],
) -> float:
    """
    Calculate the probability of a specific path occurring.

    Multiplies probabilities along the path:
      P(path) = P(n1→n2) × P(n2→n3) × ...
    """
    if len(path) < 2:
        return 1.0

    prob = 1.0
    for i in range(len(path) - 1):
        source = path[i]
        target = path[i + 1]

        if source in edge_map and target in edge_map[source]:
            prob *= edge_map[source][target]
        else:
            # Edge not found - assume low probability
            prob *= 0.1

    return prob


def enumerate_paths(
    start_node: str,
    nodes: dict[str, PostmastersNode],
    max_depth: int = 5,
) -> list[list[str]]:
    """
    Enumerate all paths from a start node to terminal nodes.

    Returns:
        List of paths, where each path is a list of node IDs
    """
    paths = []

    def dfs(current_path: list[str], depth: int):
        if depth >= max_depth:
            paths.append(list(current_path))
            return

        current_id = current_path[-1]
        node = nodes.get(current_id)

        if not node or not node.children:
            # Terminal node
            paths.append(list(current_path))
            return

        for child_id in node.children:
            if child_id in nodes:
                current_path.append(child_id)
                dfs(current_path, depth + 1)
                current_path.pop()

    dfs([start_node], 0)
    return paths


def calculate_expected_networth(
    program: dict,
    ecosystem: Optional[LocationEcosystem] = None,
    lifestyle: str = "frugal",
    family_year: int = FAMILY_TRANSITION_YEAR,
    aid_scenario: str = "no_aid",
) -> dict:
    """
    Calculate probability-weighted expected net worth across all paths.

    Returns expected value plus distribution (p10, p25, p50, p75, p90).

    Args:
        program: Program dict with salary and tuition data
        ecosystem: Location ecosystem. If None, inferred from program.
        lifestyle: "frugal" or "comfortable" living cost tier
        family_year: Calendar year for single→family transition
        aid_scenario: Financial aid scenario

    Returns:
        Dict with expected_networth_k, distribution, and all path results
    """
    nodes = get_postmasters_nodes()
    edges_by_source = get_edges_by_source()

    # Infer ecosystem from program if not provided
    if ecosystem is None:
        primary_market = program.get("primary_market") or ""
        uni_country = program.get("country") or "USA"
        market = get_market_info(primary_market, uni_country)
        eco = get_ecosystem(market.work_city, market.work_country)
        if eco is None:
            eco = get_ecosystem_by_country(market.work_country)
        ecosystem = eco

    # Calibrate edges for this ecosystem
    edge_map = calibrate_and_normalize_edges(edges_by_source, ecosystem)

    # Enumerate all paths from root
    all_paths = enumerate_paths("pm_root", nodes)

    # Calculate net worth and probability for each path
    path_results = []
    for path in all_paths:
        # Calculate path net worth
        path_nw = calculate_postmasters_path_networth(
            program, path, ecosystem, lifestyle, family_year, aid_scenario
        )

        # Calculate path probability
        path_prob = calculate_path_probability(path, edge_map)

        path_results.append({
            "path": path,
            "path_description": path_nw["path_description"],
            "net_worth_k": path_nw["path_net_worth_k"],
            "probability": round(path_prob, 6),
            "weighted_nw_k": round(path_nw["path_net_worth_k"] * path_prob, 2),
        })

    # Sort by net worth for percentile calculations
    path_results.sort(key=lambda x: x["net_worth_k"])

    # Calculate expected value (probability-weighted sum)
    expected_nw = sum(p["weighted_nw_k"] for p in path_results)

    # Calculate distribution percentiles
    net_worths = [p["net_worth_k"] for p in path_results]
    probs = [p["probability"] for p in path_results]

    # Normalize probabilities (should sum to ~1.0 already)
    total_prob = sum(probs)
    if total_prob > 0:
        norm_probs = [p / total_prob for p in probs]
    else:
        norm_probs = [1.0 / len(probs)] * len(probs)

    # Calculate weighted percentiles
    cumulative_prob = 0.0
    p10, p25, p50, p75, p90 = None, None, None, None, None

    for i, (nw, prob) in enumerate(zip(net_worths, norm_probs)):
        cumulative_prob += prob
        if p10 is None and cumulative_prob >= 0.10:
            p10 = nw
        if p25 is None and cumulative_prob >= 0.25:
            p25 = nw
        if p50 is None and cumulative_prob >= 0.50:
            p50 = nw
        if p75 is None and cumulative_prob >= 0.75:
            p75 = nw
        if p90 is None and cumulative_prob >= 0.90:
            p90 = nw

    # Sort results by weighted contribution for display
    path_results.sort(key=lambda x: x["weighted_nw_k"], reverse=True)

    return {
        "program_id": program.get("id"),
        "expected_networth_k": round(expected_nw, 2),
        "distribution": {
            "p10": round(p10, 2) if p10 else net_worths[0] if net_worths else 0,
            "p25": round(p25, 2) if p25 else net_worths[0] if net_worths else 0,
            "p50_median": round(p50, 2) if p50 else expected_nw,
            "p75": round(p75, 2) if p75 else net_worths[-1] if net_worths else 0,
            "p90": round(p90, 2) if p90 else net_worths[-1] if net_worths else 0,
        },
        "ecosystem": {
            "city": ecosystem.city if ecosystem else None,
            "startup_strength": ecosystem.startup_ecosystem_strength if ecosystem else 1.0,
            "bigtech_presence": ecosystem.bigtech_presence if ecosystem else "none",
        },
        "num_paths": len(path_results),
        "top_paths": path_results[:10],  # Top 10 by weighted contribution
    }


def compare_program_ecosystems(
    program: dict,
    cities: list[str] = None,
    lifestyle: str = "frugal",
) -> list[dict]:
    """
    Compare expected net worth for a program across different ecosystems.

    Useful for showing how the same program leads to different outcomes
    depending on where you work after graduation.

    Args:
        program: Program dict
        cities: List of cities to compare. If None, uses default set.
        lifestyle: Living cost tier

    Returns:
        List of expected networth results for each city
    """
    if cities is None:
        cities = [
            "San Francisco", "New York", "Seattle", "Austin",
            "London", "Toronto", "Singapore", "Berlin",
            "Lahore",  # Return to Pakistan comparison
        ]

    results = []
    for city in cities:
        ecosystem = get_ecosystem(city)
        if ecosystem is None:
            continue

        expected = calculate_expected_networth(
            program, ecosystem, lifestyle=lifestyle
        )

        results.append({
            "city": city,
            "country": ecosystem.country,
            "expected_networth_k": expected["expected_networth_k"],
            "p50_median_k": expected["distribution"]["p50_median"],
            "p90_k": expected["distribution"]["p90"],
            "startup_strength": ecosystem.startup_ecosystem_strength,
            "bigtech_presence": ecosystem.bigtech_presence,
        })

    # Sort by expected net worth
    results.sort(key=lambda x: x["expected_networth_k"], reverse=True)
    return results
