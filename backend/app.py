"""
Flask API for Career Decision Tree
Serves program data from SQLite database
"""

from flask import Flask, jsonify, request
from flask_cors import CORS
import json
from typing import Optional, Tuple, Union

from config import get_db, setup_logging, get_logger

setup_logging()
logger = get_logger(__name__)

app = Flask(__name__)
CORS(app)  # Enable CORS for React frontend


# ─── Global Error Handlers ───────────────────────────────────────────────────


@app.errorhandler(404)
def not_found(e):
    """Return JSON instead of HTML for 404 errors."""
    return jsonify({"error": "Resource not found"}), 404


@app.errorhandler(ValueError)
def handle_value_error(e):
    """Catch unhandled ValueErrors and return a 400 JSON response."""
    logger.warning("ValueError: %s", e)
    return jsonify({"error": str(e)}), 400


@app.errorhandler(Exception)
def handle_exception(e):
    """Catch-all for unhandled exceptions — return a 500 JSON response."""
    logger.exception("Unhandled exception: %s", e)
    return jsonify({"error": "Internal server error"}), 500


# ─── Request Validation Helpers ──────────────────────────────────────────────


def _parse_lifestyle() -> Union[str, Tuple]:
    """
    Parse and validate the 'lifestyle' query parameter.
    Returns the validated string, or a (jsonify(...), 400) error tuple.
    """
    lifestyle = request.args.get("lifestyle", "frugal")
    if lifestyle not in ("frugal", "comfortable"):
        return jsonify({"error": "lifestyle must be 'frugal' or 'comfortable'"}), 400
    return lifestyle


def _parse_family_year(max_year: int = 13) -> Union[Optional[int], Tuple]:
    """
    Parse and validate the 'family_year' query parameter.
    Returns the validated int (or None), or a (jsonify(...), 400) error tuple.

    Args:
        max_year: Upper bound for family_year (13 for masters, 11 for career paths).
    """
    raw = request.args.get("family_year")
    if not raw:
        return None
    try:
        family_year = int(raw)
        if not (1 <= family_year <= max_year):
            return jsonify(
                {
                    "error": f"family_year must be between 1 and {max_year} ({max_year} = never)"
                }
            ), 400
        return family_year
    except (ValueError, TypeError):
        return jsonify(
            {"error": f"family_year must be an integer between 1 and {max_year}"}
        ), 400


def _parse_int_param(name: str) -> Union[Optional[int], Tuple]:
    """
    Parse an optional integer query parameter safely.
    Returns the validated int (or None), or a (jsonify(...), 400) error tuple.
    """
    raw = request.args.get(name)
    if not raw:
        return None
    try:
        return int(raw)
    except (ValueError, TypeError):
        return jsonify({"error": f"'{name}' must be a valid integer"}), 400


def _parse_float_param(name: str) -> Union[Optional[float], Tuple]:
    """
    Parse an optional float query parameter safely.
    Returns the validated float (or None), or a (jsonify(...), 400) error tuple.
    """
    raw = request.args.get(name)
    if not raw:
        return None
    try:
        return float(raw)
    except (ValueError, TypeError):
        return jsonify({"error": f"'{name}' must be a valid number"}), 400


@app.route("/api/health", methods=["GET"])
def health():
    """Health check endpoint"""
    return jsonify({"status": "ok", "message": "Career Tree API is running"})


@app.route("/api/programs", methods=["GET"])
def get_programs():
    """
    Get all programs with optional filters
    Query params:
      - field: Filter by field (AI/ML, CS/SWE, etc.)
      - funding_tier: Filter by tier
      - country: Filter by country
      - max_tuition: Max tuition in USD (thousands)
      - min_y10_salary: Min year 10 salary (thousands)
    """
    # Validate params before opening connection
    max_tuition = None
    if request.args.get("max_tuition"):
        max_tuition = _parse_int_param("max_tuition")
        if isinstance(max_tuition, tuple):
            return max_tuition

    min_salary = None
    if request.args.get("min_y10_salary"):
        min_salary = _parse_int_param("min_y10_salary")
        if isinstance(min_salary, tuple):
            return min_salary

    with get_db() as conn:
        cursor = conn.cursor()

        # Base query
        query = """
            SELECT
                p.id, p.program_name, p.field, p.tuition_usd,
                p.y1_salary_usd, p.y5_salary_usd, p.y10_salary_usd,
                p.p90_y10_usd, p.net_10yr_usd, p.funding_tier,
                p.primary_market, p.key_employers, p.notes,
                u.name as university_name, u.country, u.region, u.tier as university_tier
            FROM programs p
            JOIN universities u ON p.university_id = u.id
            WHERE 1=1
        """

        params = []

        # Apply filters
        if request.args.get("field"):
            query += " AND p.field = ?"
            params.append(request.args.get("field"))

        if request.args.get("funding_tier"):
            query += " AND p.funding_tier = ?"
            params.append(request.args.get("funding_tier"))

        if request.args.get("country"):
            query += " AND u.country = ?"
            params.append(request.args.get("country"))

        if max_tuition is not None:
            query += " AND p.tuition_usd <= ?"
            params.append(max_tuition)

        if min_salary is not None:
            query += " AND p.y10_salary_usd >= ?"
            params.append(min_salary)

        # Execute query
        cursor.execute(query, params)
        rows = cursor.fetchall()

        # Convert to list of dicts
        programs = [dict(row) for row in rows]

    return jsonify({"count": len(programs), "programs": programs})


@app.route("/api/programs/<int:program_id>", methods=["GET"])
def get_program(program_id):
    """Get a specific program by ID"""
    with get_db() as conn:
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT
                p.*, u.name as university_name, u.country, u.region, u.tier as university_tier
            FROM programs p
            JOIN universities u ON p.university_id = u.id
            WHERE p.id = ?
        """,
            (program_id,),
        )

        row = cursor.fetchone()

    if row:
        return jsonify(dict(row))
    else:
        return jsonify({"error": "Program not found"}), 404


@app.route("/api/universities", methods=["GET"])
def get_universities():
    """Get all universities with program counts"""
    with get_db() as conn:
        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                u.id, u.name, u.country, u.region, u.tier,
                COUNT(p.id) as program_count
            FROM universities u
            LEFT JOIN programs p ON u.id = p.university_id
            GROUP BY u.id
            ORDER BY program_count DESC, u.name
        """)

        rows = cursor.fetchall()
        universities = [dict(row) for row in rows]

    return jsonify({"count": len(universities), "universities": universities})


@app.route("/api/stats", methods=["GET"])
def get_stats():
    """Get summary statistics"""
    with get_db() as conn:
        cursor = conn.cursor()

        # Total counts
        cursor.execute("SELECT COUNT(*) FROM programs")
        total_programs = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM universities")
        total_universities = cursor.fetchone()[0]

        # By funding tier
        cursor.execute("""
            SELECT funding_tier, COUNT(*) as count
            FROM programs
            GROUP BY funding_tier
        """)
        by_tier = {row["funding_tier"]: row["count"] for row in cursor.fetchall()}

        # By field
        cursor.execute("""
            SELECT field, COUNT(*) as count
            FROM programs
            GROUP BY field
            ORDER BY count DESC
        """)
        by_field = [dict(row) for row in cursor.fetchall()]

        # By country (top 10)
        cursor.execute("""
            SELECT u.country, COUNT(p.id) as count
            FROM universities u
            JOIN programs p ON u.id = p.university_id
            GROUP BY u.country
            ORDER BY count DESC
            LIMIT 10
        """)
        by_country = [dict(row) for row in cursor.fetchall()]

        # Salary stats
        cursor.execute("""
            SELECT
                MIN(y1_salary_usd) as min_y1,
                MAX(y1_salary_usd) as max_y1,
                AVG(y1_salary_usd) as avg_y1,
                MIN(y10_salary_usd) as min_y10,
                MAX(y10_salary_usd) as max_y10,
                AVG(y10_salary_usd) as avg_y10
            FROM programs
            WHERE y1_salary_usd IS NOT NULL AND y10_salary_usd IS NOT NULL
        """)
        salary_stats = dict(cursor.fetchone())

    return jsonify(
        {
            "total_programs": total_programs,
            "total_universities": total_universities,
            "by_tier": by_tier,
            "by_field": by_field,
            "by_country": by_country,
            "salary_stats": salary_stats,
        }
    )


@app.route("/api/career-nodes", methods=["GET"])
def get_career_nodes():
    """
    Get all career nodes with optional filter
    Query params:
      - node_type: Filter by type (career, trading, startup, freelance)
    """
    with get_db() as conn:
        cursor = conn.cursor()

        query = "SELECT * FROM career_nodes WHERE 1=1"
        params = []

        if request.args.get("node_type"):
            query += " AND node_type = ?"
            params.append(request.args.get("node_type"))

        query += " ORDER BY phase, id"
        cursor.execute(query, params)
        rows = cursor.fetchall()

        # Convert to list of dicts, parse children JSON, map probability -> prob
        nodes = []
        for row in rows:
            node = dict(row)
            # Parse children from JSON string to array
            node["children"] = json.loads(node.get("children") or "[]")
            # Map probability -> prob for frontend compatibility
            node["prob"] = node.pop("probability", None)
            nodes.append(node)

    return jsonify({"count": len(nodes), "nodes": nodes})


@app.route("/api/career-nodes/<string:node_id>", methods=["GET"])
def get_career_node(node_id):
    """Get a specific career node by ID"""
    with get_db() as conn:
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM career_nodes WHERE id = ?", (node_id,))
        row = cursor.fetchone()

    if row:
        node = dict(row)
        node["children"] = json.loads(node.get("children") or "[]")
        node["prob"] = node.pop("probability", None)
        return jsonify(node)
    else:
        return jsonify({"error": "Career node not found"}), 404


@app.route("/api/edges", methods=["GET"])
def get_edges():
    """
    Get all edges (parent-child relationships with probabilities).
    Query params:
      - source_id: Filter by source node ID
      - target_id: Filter by target node ID
      - link_type: Filter by link type (child, transition, enables, fallback)
      - node_type: Filter edges where source node matches this node_type
      - calibrated: If "true", apply profile-based probability calibration
    """
    with get_db() as conn:
        cursor = conn.cursor()

        # Check if calibrated edges requested
        if request.args.get("calibrated", "").lower() == "true":
            from profile_calibrator import calibrate_edges, get_profile

            profile = get_profile(conn)
            all_edges = calibrate_edges(profile=profile, conn=conn)

            # Apply filters
            edges = all_edges
            if request.args.get("source_id"):
                edges = [
                    e for e in edges if e["source_id"] == request.args.get("source_id")
                ]
            if request.args.get("target_id"):
                edges = [
                    e for e in edges if e["target_id"] == request.args.get("target_id")
                ]
            if request.args.get("link_type"):
                edges = [
                    e for e in edges if e["link_type"] == request.args.get("link_type")
                ]
            if request.args.get("node_type"):
                # Need to look up which nodes match the node_type
                cursor.execute(
                    "SELECT id FROM career_nodes WHERE node_type = ?",
                    (request.args.get("node_type"),),
                )
                valid_sources = {row["id"] for row in cursor.fetchall()}
                edges = [e for e in edges if e["source_id"] in valid_sources]

            return jsonify({"count": len(edges), "edges": edges, "calibrated": True})

        query = "SELECT e.* FROM edges e WHERE 1=1"
        params = []

        if request.args.get("source_id"):
            query += " AND e.source_id = ?"
            params.append(request.args.get("source_id"))

        if request.args.get("target_id"):
            query += " AND e.target_id = ?"
            params.append(request.args.get("target_id"))

        if request.args.get("link_type"):
            query += " AND e.link_type = ?"
            params.append(request.args.get("link_type"))

        if request.args.get("node_type"):
            query += (
                " AND e.source_id IN (SELECT id FROM career_nodes WHERE node_type = ?)"
            )
            params.append(request.args.get("node_type"))

        query += " ORDER BY e.source_id, e.target_id"
        cursor.execute(query, params)
        rows = cursor.fetchall()

        edges = [dict(row) for row in rows]

    return jsonify({"count": len(edges), "edges": edges})


@app.route("/api/profile", methods=["GET"])
def get_profile():
    """
    Get the current user profile used for probability calibration.
    Returns all 13 profile factors with their current values.
    """
    from profile_calibrator import get_profile as _get_profile

    with get_db() as conn:
        profile = _get_profile(conn)

    return jsonify({"profile": profile})


@app.route("/api/profile", methods=["PUT"])
def update_profile():
    """
    Update user profile for probability calibration.
    Accepts partial updates — only provided fields are changed.

    Body (JSON): any subset of profile fields:
      - years_experience: float (>= 0)
      - performance_rating: "top" | "strong" | "average" | "below"
      - risk_tolerance: "high" | "moderate" | "low"
      - available_savings_usd: int (>= 0)
      - english_level: "native" | "professional" | "intermediate" | "basic"
      - gpa: float (0-4.0) or null
      - gre_score: int (260-340) or null
      - ielts_score: float (0-9.0) or null
      - has_publications: 0 | 1
      - has_freelance_profile: 0 | 1
      - has_side_projects: 0 | 1
      - quant_aptitude: "strong" | "moderate" | "weak"
      - current_salary_pkr: int (>= 0)
    """
    from profile_calibrator import save_profile, get_profile as _get_profile

    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body must be JSON"}), 400

    try:
        with get_db() as conn:
            # Load current profile, merge with updates
            current = _get_profile(conn)
            current.update(data)
            saved = save_profile(current, conn)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    return jsonify({"profile": saved, "message": "Profile updated"})


@app.route("/api/calibration-summary", methods=["GET"])
def get_calibration_summary():
    """
    Get a summary of how the current profile affects edge probabilities.
    Shows which edges changed and by how much.
    """
    from profile_calibrator import get_calibration_summary as _get_summary

    with get_db() as conn:
        summary = _get_summary(conn=conn)

    return jsonify(summary)


@app.route("/api/search", methods=["GET"])
def search():
    """
    Search programs by keyword
    Query param: q (search query)
    """
    query_text = request.args.get("q", "")

    if not query_text:
        return jsonify({"error": "Query parameter 'q' is required"}), 400

    with get_db() as conn:
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT
                p.id, p.program_name, p.field, p.tuition_usd,
                p.y1_salary_usd, p.y10_salary_usd, p.funding_tier,
                u.name as university_name, u.country
            FROM programs p
            JOIN universities u ON p.university_id = u.id
            WHERE
                p.program_name LIKE ? OR
                u.name LIKE ? OR
                p.field LIKE ? OR
                u.country LIKE ?
            ORDER BY p.y10_salary_usd DESC
        """,
            (
                f"%{query_text}%",
                f"%{query_text}%",
                f"%{query_text}%",
                f"%{query_text}%",
            ),
        )

        rows = cursor.fetchall()
        results = [dict(row) for row in rows]

    return jsonify({"query": query_text, "count": len(results), "results": results})


def _parse_aid_scenario():
    """
    Parse and validate the 'aid_scenario' query parameter.
    Returns the validated string, or a (jsonify(...), 400) error tuple.
    """
    scenario = request.args.get("aid_scenario", "no_aid")
    if scenario not in ("no_aid", "expected", "best_case"):
        return jsonify({"error": "aid_scenario must be 'no_aid', 'expected', or 'best_case'"}), 400
    return scenario


@app.route("/api/networth", methods=["GET"])
def get_networth():
    """
    Calculate 12-year net worth for all programs (V2).
    Uses progressive tax brackets per country and real per-city living costs.

    Query params (all optional):
      - baseline_salary: Current annual salary in $K USD (default: 9.5)
      - baseline_growth: Annual salary growth rate (default: 0.08)
      - lifestyle: Living cost tier — "frugal" or "comfortable" (default: frugal)
      - family_year: Calendar year for single→family transition, 1-13 (default: 5, 13=never)
      - aid_scenario: Financial aid scenario — "no_aid", "expected", or "best_case" (default: no_aid)
      - sort_by: Sort field — net_benefit, cost, y1, y10, networth, initial_capital (default: net_benefit)
      - field: Filter by field (AI/ML, CS/SWE, etc.)
      - funding_tier: Filter by tier
      - work_country: Filter by work country
      - max_initial_capital: Max initial capital requirement in USD (filters programs you can afford)
      - limit: Max results (default: all)
      - compact: If "true", omit yearly breakdowns (default: false)
    """
    from networth_calculator import calculate_all_programs

    # Parse optional baseline overrides from query params
    baseline_salary = _parse_float_param("baseline_salary")
    if isinstance(baseline_salary, tuple):
        return baseline_salary
    baseline_growth = _parse_float_param("baseline_growth")
    if isinstance(baseline_growth, tuple):
        return baseline_growth

    # Parse lifestyle tier
    lifestyle = _parse_lifestyle()
    if isinstance(lifestyle, tuple):
        return lifestyle

    # Parse family transition year
    family_transition_year = _parse_family_year(max_year=13)
    if isinstance(family_transition_year, tuple):
        return family_transition_year

    # Parse aid scenario
    aid_scenario = _parse_aid_scenario()
    if isinstance(aid_scenario, tuple):
        return aid_scenario

    data = calculate_all_programs(
        baseline_salary=baseline_salary,
        baseline_growth=baseline_growth,
        lifestyle=lifestyle,
        family_transition_year=family_transition_year,
        aid_scenario=aid_scenario,
    )

    # Filter
    programs = data["programs"]
    if request.args.get("field"):
        programs = [p for p in programs if p["field"] == request.args.get("field")]
    if request.args.get("funding_tier"):
        programs = [
            p for p in programs if p["funding_tier"] == request.args.get("funding_tier")
        ]
    if request.args.get("work_country"):
        programs = [
            p for p in programs if p["work_country"] == request.args.get("work_country")
        ]

    # Filter by max initial capital (affordability filter)
    max_capital = _parse_int_param("max_initial_capital")
    if isinstance(max_capital, tuple):
        return max_capital
    if max_capital is not None:
        programs = [
            p for p in programs if p.get("initial_capital_usd", 0) <= max_capital
        ]

    # Sort
    sort_key = request.args.get("sort_by", "net_benefit")
    sort_map = {
        "net_benefit": "net_benefit_k",
        "cost": "total_study_cost_k",
        "y1": "y1_salary_k",
        "y10": "y10_salary_k",
        "networth": "masters_networth_k",
        "initial_capital": "initial_capital_usd",
    }
    key = sort_map.get(sort_key, "net_benefit_k")
    # For initial_capital, lower is better; for cost, lower is also better
    reverse = sort_key not in ("cost", "initial_capital")
    programs.sort(key=lambda x: x.get(key, 0), reverse=reverse)

    # Limit
    limit = _parse_int_param("limit")
    if isinstance(limit, tuple):
        return limit
    if limit is not None:
        programs = programs[:limit]

    # Compact mode — strip yearly breakdowns
    if request.args.get("compact", "").lower() == "true":
        for p in programs:
            p.pop("yearly_breakdown", None)

    data["programs"] = programs
    data["summary"]["total_filtered"] = len(programs)

    return jsonify(data)


@app.route("/api/networth/<int:program_id>", methods=["GET"])
def get_program_networth(program_id):
    """
    Calculate 12-year net worth for a specific program by ID (V2).

    Query params (all optional):
      - lifestyle: Living cost tier — "frugal" or "comfortable" (default: frugal)
      - family_year: Calendar year for single→family transition, 1-13 (default: 5, 13=never)
      - aid_scenario: Financial aid scenario — "no_aid", "expected", or "best_case" (default: no_aid)
    """
    from networth_calculator import (
        calculate_program_networth,
        calculate_baseline_networth,
    )

    # Parse lifestyle tier
    lifestyle = _parse_lifestyle()
    if isinstance(lifestyle, tuple):
        return lifestyle

    # Parse family transition year
    family_transition_year = _parse_family_year(max_year=13)
    if isinstance(family_transition_year, tuple):
        return family_transition_year

    # Parse aid scenario
    aid_scenario = _parse_aid_scenario()
    if isinstance(aid_scenario, tuple):
        return aid_scenario

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
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
            WHERE p.id = ?
        """,
            (program_id,),
        )

        row = cursor.fetchone()

    if not row:
        return jsonify({"error": "Program not found"}), 404

    program = dict(row)
    baseline = calculate_baseline_networth(
        lifestyle=lifestyle,
        family_transition_year=family_transition_year,
    )
    result = calculate_program_networth(
        program,
        baseline["total_networth_k"],
        lifestyle=lifestyle,
        family_transition_year=family_transition_year,
        aid_scenario=aid_scenario,
    )
    result["baseline"] = baseline

    return jsonify(result)


@app.route("/api/networth/<int:program_id>/compare", methods=["GET"])
def get_program_networth_comparison(program_id):
    """
    Calculate 12-year net worth for a specific program with ALL THREE aid scenarios.
    Returns no_aid, expected, and best_case scenarios for comparison.

    Query params (all optional):
      - lifestyle: Living cost tier — "frugal" or "comfortable" (default: frugal)
      - family_year: Calendar year for single→family transition, 1-13 (default: 5, 13=never)
    """
    from networth_calculator import (
        calculate_program_networth,
        calculate_baseline_networth,
    )

    # Parse lifestyle tier
    lifestyle = _parse_lifestyle()
    if isinstance(lifestyle, tuple):
        return lifestyle

    # Parse family transition year
    family_transition_year = _parse_family_year(max_year=13)
    if isinstance(family_transition_year, tuple):
        return family_transition_year

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
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
            WHERE p.id = ?
        """,
            (program_id,),
        )

        row = cursor.fetchone()

    if not row:
        return jsonify({"error": "Program not found"}), 404

    program = dict(row)
    baseline = calculate_baseline_networth(
        lifestyle=lifestyle,
        family_transition_year=family_transition_year,
    )

    # Calculate all three scenarios
    scenarios = {}
    for scenario in ["no_aid", "expected", "best_case"]:
        result = calculate_program_networth(
            program,
            baseline["total_networth_k"],
            lifestyle=lifestyle,
            family_transition_year=family_transition_year,
            aid_scenario=scenario,
        )
        # Remove yearly breakdown for compactness
        result.pop("yearly_breakdown", None)
        scenarios[scenario] = result

    # Calculate aid impact
    aid_impact_expected = scenarios["expected"]["net_benefit_k"] - scenarios["no_aid"]["net_benefit_k"]
    aid_impact_best_case = scenarios["best_case"]["net_benefit_k"] - scenarios["no_aid"]["net_benefit_k"]

    return jsonify({
        "program_id": program_id,
        "university": program["university_name"],
        "program_name": program["program_name"],
        "country": program["country"],
        "raw_tuition_k": program["tuition_usd"],
        "aid_type": program["aid_type"],
        "expected_aid_k": program["expected_aid_usd"],
        "best_case_aid_k": program["best_case_aid_usd"],
        "coop_earnings_k": program["coop_earnings_usd"],
        "baseline": baseline,
        "scenarios": scenarios,
        "aid_impact": {
            "expected_vs_no_aid_k": round(aid_impact_expected, 2),
            "best_case_vs_no_aid_k": round(aid_impact_best_case, 2),
        },
        "summary": {
            "no_aid_net_benefit_k": scenarios["no_aid"]["net_benefit_k"],
            "expected_net_benefit_k": scenarios["expected"]["net_benefit_k"],
            "best_case_net_benefit_k": scenarios["best_case"]["net_benefit_k"],
        }
    })


@app.route("/api/affordability", methods=["GET"])
def get_affordability():
    """
    Get programs filtered by affordability based on user's available savings.
    Shows which programs the user can realistically start with their current funds.

    Query params (all optional):
      - available_savings: Available initial capital in USD (default: from user profile)
      - monthly_side_income: Expected monthly side income during prep period in USD (default: 0)
      - prep_months: Months until program start to save more (default: 6)
      - aid_scenario: Financial aid scenario — "no_aid", "expected", or "best_case" (default: expected)

    Returns programs grouped by affordability tier:
      - affordable: Initial capital <= available funds
      - stretch: Initial capital <= available + (monthly_income * prep_months)
      - needs_funding: Requires external loans or family support
    """
    from networth_calculator import calculate_all_programs
    from profile_calibrator import get_profile as _get_profile

    # Get user's available savings from profile if not specified
    available_savings = _parse_int_param("available_savings")
    if isinstance(available_savings, tuple):
        return available_savings

    if available_savings is None:
        with get_db() as conn:
            profile = _get_profile(conn)
            available_savings = profile.get("available_savings_usd", 5000)

    # Parse other params
    monthly_side_income = _parse_int_param("monthly_side_income")
    if isinstance(monthly_side_income, tuple):
        return monthly_side_income
    monthly_side_income = monthly_side_income or 0

    prep_months = _parse_int_param("prep_months")
    if isinstance(prep_months, tuple):
        return prep_months
    prep_months = prep_months or 6

    # Parse aid scenario (default to expected for affordability calculations)
    aid_scenario = request.args.get("aid_scenario", "expected")
    if aid_scenario not in ("no_aid", "expected", "best_case"):
        return jsonify({"error": "aid_scenario must be 'no_aid', 'expected', or 'best_case'"}), 400

    # Calculate total available funds
    total_available = available_savings + (monthly_side_income * prep_months)

    # Get all programs
    data = calculate_all_programs(aid_scenario=aid_scenario)
    programs = data["programs"]

    # Group by affordability
    affordable = []
    stretch = []
    needs_funding = []

    for p in programs:
        initial_capital = p.get("initial_capital_usd", 0)
        shortfall = initial_capital - total_available

        p["initial_capital_usd"] = initial_capital
        p["shortfall_usd"] = max(0, shortfall)
        p["affordability_pct"] = round(min(100, (total_available / max(initial_capital, 1)) * 100), 1)

        if initial_capital <= available_savings:
            p["affordability_tier"] = "affordable"
            affordable.append(p)
        elif initial_capital <= total_available:
            p["affordability_tier"] = "stretch"
            stretch.append(p)
        else:
            p["affordability_tier"] = "needs_funding"
            needs_funding.append(p)

    # Sort each group by net benefit
    for group in [affordable, stretch, needs_funding]:
        group.sort(key=lambda x: x.get("net_benefit_k", 0), reverse=True)

    # Remove yearly breakdown for compactness
    for group in [affordable, stretch, needs_funding]:
        for p in group:
            p.pop("yearly_breakdown", None)

    return jsonify({
        "available_savings_usd": available_savings,
        "monthly_side_income_usd": monthly_side_income,
        "prep_months": prep_months,
        "total_available_usd": total_available,
        "aid_scenario": aid_scenario,
        "summary": {
            "affordable_count": len(affordable),
            "stretch_count": len(stretch),
            "needs_funding_count": len(needs_funding),
            "total_programs": len(programs),
        },
        "affordable": affordable,
        "stretch": stretch,
        "needs_funding": needs_funding[:20],  # Limit needs_funding to top 20
    })



    """
    Get scholarship information for programs.
    Returns aggregated scholarship data by aid type and funding tier.

    Query params (all optional):
      - aid_type: Filter by aid type (guaranteed_funding, govt_scholarship, ta_ra, merit, etc.)
      - country: Filter by university country
      - min_expected_aid: Minimum expected aid in $K
    """
    with get_db() as conn:
        cursor = conn.cursor()

        query = """
            SELECT
                p.id, p.program_name, p.tuition_usd, p.funding_tier,
                p.expected_aid_pct, p.expected_aid_usd,
                p.best_case_aid_pct, p.best_case_aid_usd,
                p.aid_type, p.coop_earnings_usd,
                u.name as university_name, u.country
            FROM programs p
            JOIN universities u ON p.university_id = u.id
            WHERE 1=1
        """
        params = []

        if request.args.get("aid_type"):
            query += " AND p.aid_type = ?"
            params.append(request.args.get("aid_type"))

        if request.args.get("country"):
            query += " AND u.country = ?"
            params.append(request.args.get("country"))

        min_aid = _parse_int_param("min_expected_aid")
        if isinstance(min_aid, tuple):
            return min_aid
        if min_aid is not None:
            query += " AND p.expected_aid_usd >= ?"
            params.append(min_aid)

        query += " ORDER BY p.best_case_aid_usd DESC, p.expected_aid_usd DESC"

        cursor.execute(query, params)
        rows = cursor.fetchall()
        programs = [dict(row) for row in rows]

    # Generate summary by aid type
    aid_type_summary = {}
    for p in programs:
        aid_type = p["aid_type"] or "none"
        if aid_type not in aid_type_summary:
            aid_type_summary[aid_type] = {
                "count": 0,
                "avg_expected_aid_k": 0,
                "avg_best_case_aid_k": 0,
                "total_expected": 0,
                "total_best_case": 0,
            }
        aid_type_summary[aid_type]["count"] += 1
        aid_type_summary[aid_type]["total_expected"] += p["expected_aid_usd"] or 0
        aid_type_summary[aid_type]["total_best_case"] += p["best_case_aid_usd"] or 0

    for aid_type, data in aid_type_summary.items():
        if data["count"] > 0:
            data["avg_expected_aid_k"] = round(data["total_expected"] / data["count"], 1)
            data["avg_best_case_aid_k"] = round(data["total_best_case"] / data["count"], 1)
        del data["total_expected"]
        del data["total_best_case"]

    return jsonify({
        "count": len(programs),
        "programs": programs,
        "by_aid_type": aid_type_summary,
    })


# ═══════════════════════════════════════════════════════════════════════════
# Career Path Net Worth Endpoints (Trading / Startup / Freelance / Career)
# ═══════════════════════════════════════════════════════════════════════════


@app.route("/api/networth/career", methods=["GET"])
def get_career_networth():
    """
    Calculate 10-year net worth for all career path nodes.
    These are non-masters paths (career, trading, startup, freelance)
    that stay in Pakistan.

    Query params (all optional):
      - node_type: Filter by type — "career", "trading", "startup", "freelance"
      - leaf_only: If "true" (default), only calculate for leaf nodes
      - lifestyle: Living cost tier — "frugal" or "comfortable" (default: frugal)
      - family_year: Calendar year for single→family transition, 1-10
          (default: 3, 11=never)
      - sort_by: Sort field — net_benefit, y1, y10, networth (default: net_benefit)
      - limit: Max results (default: all)
      - compact: If "true", omit yearly breakdowns (default: false)
    """
    from career_networth_calculator import calculate_all_career_paths

    # Parse node_type filter
    node_type = request.args.get("node_type")
    if node_type and node_type not in ("career", "trading", "startup", "freelance"):
        return jsonify(
            {
                "error": "node_type must be 'career', 'trading', 'startup', or 'freelance'"
            }
        ), 400

    # Parse leaf_only
    leaf_only = request.args.get("leaf_only", "true").lower() != "false"

    # Parse lifestyle tier
    lifestyle = _parse_lifestyle()
    if isinstance(lifestyle, tuple):
        return lifestyle

    # Parse family transition year
    family_transition_year = _parse_family_year(max_year=11)
    if isinstance(family_transition_year, tuple):
        return family_transition_year

    data = calculate_all_career_paths(
        node_type=node_type,
        leaf_only=leaf_only,
        lifestyle=lifestyle,
        family_transition_year=family_transition_year,
    )

    # Sort
    results = data["results"]
    sort_key = request.args.get("sort_by", "net_benefit")
    sort_map = {
        "net_benefit": "net_benefit_k",
        "y1": "y1_income_k",
        "y10": "y10_income_k",
        "networth": "path_networth_k",
    }
    key = sort_map.get(sort_key, "net_benefit_k")
    results.sort(key=lambda x: x.get(key, 0), reverse=True)

    # Limit
    limit = _parse_int_param("limit")
    if isinstance(limit, tuple):
        return limit
    if limit is not None:
        results = results[:limit]

    # Compact mode — strip yearly breakdowns
    if request.args.get("compact", "").lower() == "true":
        for r in results:
            r.pop("yearly_breakdown", None)

    data["results"] = results
    data["summary"]["total_filtered"] = len(results)

    return jsonify(data)


@app.route("/api/networth/career/<string:node_id>", methods=["GET"])
def get_career_node_networth(node_id):
    """
    Calculate 10-year net worth for a specific career node by ID.

    Query params (all optional):
      - lifestyle: Living cost tier — "frugal" or "comfortable" (default: frugal)
      - family_year: Calendar year for single→family transition, 1-10
          (default: 3, 11=never)
    """
    from career_networth_calculator import (
        calculate_career_node_networth,
        calculate_career_baseline,
    )

    # Parse lifestyle tier
    lifestyle = _parse_lifestyle()
    if isinstance(lifestyle, tuple):
        return lifestyle

    # Parse family transition year
    family_transition_year = _parse_family_year(max_year=11)
    if isinstance(family_transition_year, tuple):
        return family_transition_year

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM career_nodes WHERE id = ?", (node_id,))
        row = cursor.fetchone()

    if not row:
        return jsonify({"error": f"Career node '{node_id}' not found"}), 404

    node = dict(row)

    # Check node has income data
    if not node.get("y1_income_usd") and not node.get("y10_income_usd"):
        return jsonify(
            {
                "error": f"Career node '{node_id}' has no income data for net worth calculation"
            }
        ), 400

    baseline = calculate_career_baseline(
        lifestyle=lifestyle,
        family_transition_year=family_transition_year,
    )
    result = calculate_career_node_networth(
        node,
        baseline["total_networth_k"],
        lifestyle=lifestyle,
        family_transition_year=family_transition_year,
    )
    result["baseline"] = baseline

    return jsonify(result)


if __name__ == "__main__":
    print("🚀 Starting Career Tree API...")
    print("📍 API will be available at: http://localhost:5000")
    print("\n📚 Endpoints:")
    print("   GET  /api/health")
    print("   GET  /api/programs")
    print("   GET  /api/programs/<id>")
    print("   GET  /api/career-nodes")
    print("   GET  /api/career-nodes?node_type=<type>")
    print("   GET  /api/career-nodes/<id>")
    print("   GET  /api/edges")
    print("   GET  /api/edges?link_type=<type>&source_id=<id>&node_type=<type>")
    print("   GET  /api/edges?calibrated=true")
    print("   GET  /api/profile")
    print("   PUT  /api/profile")
    print("   GET  /api/calibration-summary")
    print("   GET  /api/universities")
    print("   GET  /api/stats")
    print("   GET  /api/search?q=<query>")
    print("   GET  /api/networth")
    print("   GET  /api/networth?aid_scenario=expected&field=AI/ML&compact=true")
    print("   GET  /api/networth/<program_id>")
    print("   GET  /api/networth/<program_id>?aid_scenario=best_case")
    print("   GET  /api/networth/<program_id>/compare  (all 3 aid scenarios)")
    print("   GET  /api/scholarships")
    print("   GET  /api/scholarships?aid_type=guaranteed_funding")
    print("   GET  /api/affordability")
    print("   GET  /api/affordability?available_savings=5000&monthly_side_income=2000")
    print("   GET  /api/networth/career")
    print("   GET  /api/networth/career?node_type=trading&compact=true")
    print("   GET  /api/networth/career/<node_id>")
    print("\n💰 Aid Scenarios: no_aid (default), expected, best_case")
    print("💵 Initial Capital: Filter by max_initial_capital, or use /api/affordability")
    print("\n🔗 Test it: http://localhost:5000/api/networth?aid_scenario=expected&compact=true\n")

    app.run(debug=True, host="0.0.0.0", port=5000)
