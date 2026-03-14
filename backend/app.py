"""
Flask API for Career Decision Tree
Serves program data from SQLite database
"""

from flask import Flask, jsonify, request
from flask_cors import CORS
import json

from config import get_db, setup_logging, get_logger
from validators import (
    validate_params,
    validate_optional_int,
    validate_optional_float,
    LIFESTYLE,
    AID_SCENARIO,
    FAMILY_YEAR_MASTERS,
    FAMILY_YEAR_CAREER,
    NODE_TYPE,
    NETWORTH_SORT,
    CAREER_SORT,
)

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
      - gre_required: Filter by GRE status (comma-separated: not_required,waivable,optional)
      - ielts_max: Max IELTS score required (e.g., 7.0)
      - toefl_max: Max TOEFL score required (e.g., 100)
    """
    from query_builder import QueryBuilder

    # Validate params before opening connection
    max_tuition, error = validate_optional_int(request.args, "max_tuition")
    if error:
        return error
    min_salary, error = validate_optional_int(request.args, "min_y10_salary")
    if error:
        return error
    ielts_max, error = validate_optional_float(request.args, "ielts_max")
    if error:
        return error
    toefl_max, error = validate_optional_int(request.args, "toefl_max")
    if error:
        return error

    qb = QueryBuilder("""
        SELECT
            p.id, p.program_name, p.field, p.tuition_usd,
            p.y1_salary_usd, p.y5_salary_usd, p.y10_salary_usd,
            p.p90_y10_usd, p.net_10yr_usd, p.funding_tier,
            p.primary_market, p.key_employers, p.notes,
            p.gre_required, p.gre_waiver_conditions,
            p.ielts_min_score, p.toefl_min_score, p.english_waiver_available,
            u.name as university_name, u.country, u.region, u.tier as university_tier
        FROM programs p
        JOIN universities u ON p.university_id = u.id
    """)
    qb.add_filter("p.field = ?", request.args.get("field"))
    qb.add_filter("p.funding_tier = ?", request.args.get("funding_tier"))
    qb.add_filter("u.country = ?", request.args.get("country"))
    qb.add_filter("p.tuition_usd <= ?", max_tuition)
    qb.add_filter("p.y10_salary_usd >= ?", min_salary)
    qb.add_filter("p.ielts_min_score <= ?", ielts_max)
    qb.add_filter("p.toefl_min_score <= ?", toefl_max)

    # Handle comma-separated gre_required filter
    gre_filter = request.args.get("gre_required")
    if gre_filter:
        gre_values = [v.strip() for v in gre_filter.split(",") if v.strip()]
        if gre_values:
            qb.add_in_filter("p.gre_required", gre_values)

    query, params = qb.build()

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        rows = cursor.fetchall()
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
    from query_builder import QueryBuilder

    qb = QueryBuilder("SELECT * FROM career_nodes")
    qb.add_filter("node_type = ?", request.args.get("node_type"))
    qb.order_by("phase, id")
    query, params = qb.build()

    with get_db() as conn:
        cursor = conn.cursor()
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


# ═══════════════════════════════════════════════════════════════════════════
# Quality of Life & Immigration Endpoints
# ═══════════════════════════════════════════════════════════════════════════


@app.route("/api/qol/<city>", methods=["GET"])
def get_city_qol(city):
    """
    Get quality of life metrics for a specific city.
    Returns safety, climate, halal food, Muslim community, transit, healthcare data.
    """
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM qol_metrics WHERE city = ?", (city,))
        row = cursor.fetchone()

    if row:
        return jsonify(dict(row))
    else:
        return jsonify({"error": f"QoL metrics not found for city: {city}"}), 404


@app.route("/api/qol", methods=["GET"])
def get_all_qol():
    """
    Get quality of life metrics for all cities.
    Query params (all optional):
      - country: Filter by country
      - min_safety: Minimum safety index (0-100)
      - halal: Filter by halal_food_availability ('excellent', 'good', 'limited', 'poor')
      - muslim_community: Filter by muslim_community_size ('large', 'medium', 'small', 'minimal')
    """
    from query_builder import QueryBuilder

    qb = QueryBuilder("SELECT * FROM qol_metrics")
    qb.add_filter("country = ?", request.args.get("country"))
    qb.add_filter("safety_index >= ?", request.args.get("min_safety"))
    qb.add_filter("halal_food_availability = ?", request.args.get("halal"))
    qb.add_filter("muslim_community_size = ?", request.args.get("muslim_community"))
    qb.order_by("safety_index DESC")

    query, params = qb.build()

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        rows = cursor.fetchall()
        metrics = [dict(row) for row in rows]

    return jsonify({"count": len(metrics), "qol_metrics": metrics})


@app.route("/api/visa-rates", methods=["GET"])
def get_visa_rates():
    """
    Get visa approval rates by nationality.
    Query params (all optional):
      - country: Filter by destination country
      - nationality: Filter by nationality (default: all, typically 'Pakistan')
      - visa_type: Filter by visa type (e.g., 'H-1B', 'PGWP')
    """
    from query_builder import QueryBuilder

    qb = QueryBuilder("SELECT * FROM visa_approval_by_nationality")
    qb.add_filter("country = ?", request.args.get("country"))
    qb.add_filter("nationality = ?", request.args.get("nationality"))
    qb.add_filter("visa_type = ?", request.args.get("visa_type"))
    qb.order_by("country, visa_type")

    query, params = qb.build()

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        rows = cursor.fetchall()
        rates = [dict(row) for row in rows]

    return jsonify({"count": len(rates), "visa_rates": rates})


@app.route("/api/visa-rates/<country>/<nationality>", methods=["GET"])
def get_country_visa_rates(country, nationality):
    """
    Get all visa rates for a specific country/nationality pair.
    Includes student visas, work visas, and PR pathways.
    """
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM visa_approval_by_nationality
            WHERE country = ? AND nationality = ?
            ORDER BY visa_type
        """, (country, nationality))
        rows = cursor.fetchall()
        rates = [dict(row) for row in rows]

    if not rates:
        return jsonify({"error": f"No visa data for {nationality} in {country}"}), 404

    return jsonify({
        "country": country,
        "nationality": nationality,
        "count": len(rates),
        "visa_rates": rates
    })


@app.route("/api/immigration/<country>", methods=["GET"])
def get_immigration_policy(country):
    """
    Get immigration policy for a specific country.
    Returns student visa, post-study work, PR pathway, spouse rights, etc.
    """
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM immigration_policy WHERE country = ?", (country,))
        row = cursor.fetchone()

    if row:
        return jsonify(dict(row))
    else:
        return jsonify({"error": f"Immigration policy not found for country: {country}"}), 404


@app.route("/api/immigration", methods=["GET"])
def get_all_immigration():
    """
    Get immigration policies for all countries.
    Query params (all optional):
      - spouse_work: If "true", filter to countries with spouse open work permit
      - pr_difficulty: Filter by PR pathway difficulty ('easy', 'moderate', 'difficult', 'very_difficult')
      - min_post_study_months: Minimum post-study work duration in months
    """
    from query_builder import QueryBuilder

    qb = QueryBuilder("SELECT * FROM immigration_policy")
    if request.args.get("spouse_work", "").lower() == "true":
        qb.add_filter("spouse_open_work_permit = ?", 1)
    qb.add_filter("pr_pathway_difficulty = ?", request.args.get("pr_difficulty"))
    qb.add_filter("post_study_work_duration_months >= ?", request.args.get("min_post_study_months"))
    qb.order_by("post_study_work_duration_months DESC")

    query, params = qb.build()

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        rows = cursor.fetchall()
        policies = [dict(row) for row in rows]

    return jsonify({"count": len(policies), "immigration_policies": policies})


@app.route("/api/industry-hubs/<city>", methods=["GET"])
def get_city_industry_hubs(city):
    """
    Get industry hub data for a specific city.
    Returns all industries present in the city with strength, employers, salaries.
    """
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM industry_hubs WHERE city = ?", (city,))
        rows = cursor.fetchall()
        hubs = [dict(row) for row in rows]

    if hubs:
        return jsonify({"city": city, "count": len(hubs), "hubs": hubs})
    else:
        return jsonify({"error": f"Industry hubs not found for city: {city}"}), 404


@app.route("/api/industry-hubs", methods=["GET"])
def get_all_industry_hubs():
    """
    Get industry hub data for all cities.
    Query params (all optional):
      - industry: Filter by industry ('AI/ML', 'Finance', etc.)
      - hub_strength: Filter by strength ('global_leader', 'major', 'growing', 'emerging')
    """
    from query_builder import QueryBuilder

    qb = QueryBuilder("SELECT * FROM industry_hubs")
    qb.add_filter("industry = ?", request.args.get("industry"))
    qb.add_filter("hub_strength = ?", request.args.get("hub_strength"))
    qb.order_by("avg_tech_salary_usd DESC")

    query, params = qb.build()

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        rows = cursor.fetchall()
        hubs = [dict(row) for row in rows]

    return jsonify({"count": len(hubs), "industry_hubs": hubs})


@app.route("/api/programs/<int:program_id>/full", methods=["GET"])
def get_program_full_details(program_id):
    """
    Get program with all enhanced data joined: visa info, QoL, immigration, industry hubs.
    Returns comprehensive data for decision-making.
    """
    with get_db() as conn:
        cursor = conn.cursor()

        # Get program with university info
        cursor.execute("""
            SELECT
                p.*, u.name as university_name, u.country, u.region, u.tier as university_tier
            FROM programs p
            JOIN universities u ON p.university_id = u.id
            WHERE p.id = ?
        """, (program_id,))
        program_row = cursor.fetchone()

        if not program_row:
            return jsonify({"error": "Program not found"}), 404

        program = dict(program_row)
        country = program["country"]

        # Get immigration policy for this country
        cursor.execute("SELECT * FROM immigration_policy WHERE country = ?", (country,))
        immigration_row = cursor.fetchone()
        immigration = dict(immigration_row) if immigration_row else None

        # Get QoL metrics for the primary market city (if exists)
        primary_market = program.get("primary_market", "")
        qol = None
        if primary_market:
            # Extract city from primary_market (e.g., "Bay Area, CA" -> try "San Francisco")
            from market_mapping import get_market_info
            market_info = get_market_info(primary_market, country)
            if market_info.work_city:
                cursor.execute("SELECT * FROM qol_metrics WHERE city = ?", (market_info.work_city,))
                qol_row = cursor.fetchone()
                qol = dict(qol_row) if qol_row else None

        # Get industry hubs for the work city
        industry_hubs = []
        if qol:
            cursor.execute("SELECT * FROM industry_hubs WHERE city = ?", (qol["city"],))
            industry_hubs = [dict(row) for row in cursor.fetchall()]

    # Build visa info summary
    visa_info = {
        "visa_type": program.get("visa_type"),
        "visa_duration_years": program.get("visa_duration_years"),
        "work_auth_certainty": program.get("work_auth_certainty"),
        "stem_designation": bool(program.get("stem_designation")),
        "spouse_work_permit": bool(program.get("spouse_work_permit")),
    }

    # Build placement summary
    placement_info = {
        "employment_rate_6mo": program.get("employment_rate_6mo"),
        "median_time_to_offer_weeks": program.get("median_time_to_offer_weeks"),
        "career_services_rating": program.get("career_services_rating"),
    }

    # Build cohort info
    cohort_info = {
        "avg_class_size": program.get("avg_class_size"),
        "international_student_pct": program.get("international_student_pct"),
        "pakistan_alumni_network": program.get("pakistan_alumni_network"),
    }

    # Build program structure
    program_structure = {
        "thesis_required": bool(program.get("thesis_required")),
        "capstone_project": bool(program.get("capstone_project")),
        "part_time_available": bool(program.get("part_time_available")),
        "online_hybrid_option": bool(program.get("online_hybrid_option")),
    }

    return jsonify({
        "program": program,
        "visa_info": visa_info,
        "placement_info": placement_info,
        "cohort_info": cohort_info,
        "program_structure": program_structure,
        "immigration_policy": immigration,
        "qol_metrics": qol,
        "industry_hubs": industry_hubs,
    })


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


# ─── Networth Endpoint Helpers ──────────────────────────────────────────────


def _filter_programs(programs: list, args: dict, max_capital: int = None) -> list:
    """Apply filters to program list based on request args."""
    if args.get("field"):
        programs = [p for p in programs if p["field"] == args.get("field")]
    if args.get("funding_tier"):
        programs = [p for p in programs if p["funding_tier"] == args.get("funding_tier")]
    if args.get("work_country"):
        programs = [p for p in programs if p["work_country"] == args.get("work_country")]
    if max_capital is not None:
        programs = [p for p in programs if p.get("initial_capital_usd", 0) <= max_capital]
    return programs


def _sort_programs(programs: list, sort_by: str, sort_map: dict) -> None:
    """Sort programs in place by the specified field."""
    key = sort_map.get(sort_by, "net_benefit_k")
    # For initial_capital and cost, lower is better
    reverse = sort_by not in ("cost", "initial_capital")
    programs.sort(key=lambda x: x.get(key, 0), reverse=reverse)


def _apply_compact_mode(programs: list, compact: bool) -> None:
    """Strip yearly breakdowns from programs if compact mode is enabled."""
    if compact:
        for p in programs:
            p.pop("yearly_breakdown", None)


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

    # Validate parameters
    params, error = validate_params(request.args, [LIFESTYLE, AID_SCENARIO, FAMILY_YEAR_MASTERS])
    if error:
        return error

    baseline_salary, error = validate_optional_float(request.args, "baseline_salary")
    if error:
        return error
    baseline_growth, error = validate_optional_float(request.args, "baseline_growth")
    if error:
        return error
    max_capital, error = validate_optional_int(request.args, "max_initial_capital")
    if error:
        return error
    limit, error = validate_optional_int(request.args, "limit")
    if error:
        return error

    data = calculate_all_programs(
        baseline_salary=baseline_salary,
        baseline_growth=baseline_growth,
        lifestyle=params["lifestyle"],
        family_transition_year=params["family_year"],
        aid_scenario=params["aid_scenario"],
    )

    # Filter, sort, limit, compact
    programs = _filter_programs(data["programs"], request.args, max_capital)

    sort_map = {
        "net_benefit": "net_benefit_k",
        "cost": "total_study_cost_k",
        "y1": "y1_salary_k",
        "y10": "y10_salary_k",
        "networth": "masters_networth_k",
        "initial_capital": "initial_capital_usd",
    }
    _sort_programs(programs, request.args.get("sort_by", "net_benefit"), sort_map)

    if limit is not None:
        programs = programs[:limit]

    _apply_compact_mode(programs, request.args.get("compact", "").lower() == "true")

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

    # Validate parameters
    params, error = validate_params(request.args, [LIFESTYLE, AID_SCENARIO, FAMILY_YEAR_MASTERS])
    if error:
        return error

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
        lifestyle=params["lifestyle"],
        family_transition_year=params["family_year"],
    )
    result = calculate_program_networth(
        program,
        baseline["total_networth_k"],
        lifestyle=params["lifestyle"],
        family_transition_year=params["family_year"],
        aid_scenario=params["aid_scenario"],
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

    # Validate parameters
    params, error = validate_params(request.args, [LIFESTYLE, FAMILY_YEAR_MASTERS])
    if error:
        return error

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
        lifestyle=params["lifestyle"],
        family_transition_year=params["family_year"],
    )

    # Calculate all three scenarios
    scenarios = {}
    for scenario in ["no_aid", "expected", "best_case"]:
        result = calculate_program_networth(
            program,
            baseline["total_networth_k"],
            lifestyle=params["lifestyle"],
            family_transition_year=params["family_year"],
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
    from validators import ParamValidator

    # Create aid_scenario validator with "expected" as default for affordability
    aid_scenario_expected = ParamValidator(
        name="aid_scenario",
        param_type=str,
        default="expected",
        valid_values={"no_aid", "expected", "best_case"},
        error_msg="aid_scenario must be 'no_aid', 'expected', or 'best_case'",
    )
    params, error = validate_params(request.args, [aid_scenario_expected])
    if error:
        return error

    # Get optional integer params
    available_savings, error = validate_optional_int(request.args, "available_savings")
    if error:
        return error
    monthly_side_income, error = validate_optional_int(request.args, "monthly_side_income")
    if error:
        return error
    prep_months, error = validate_optional_int(request.args, "prep_months")
    if error:
        return error

    # Get available savings from profile if not specified
    if available_savings is None:
        with get_db() as conn:
            profile = _get_profile(conn)
            available_savings = profile.get("available_savings_usd", 5000)

    monthly_side_income = monthly_side_income or 0
    prep_months = prep_months or 6
    aid_scenario = params["aid_scenario"]

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


# ═══════════════════════════════════════════════════════════════════════════
# Career Path Net Worth Endpoints (Trading / Startup / Freelance / Career)
# ═══════════════════════════════════════════════════════════════════════════


# ═══════════════════════════════════════════════════════════════════════════
# Scholarships Endpoints
# ═══════════════════════════════════════════════════════════════════════════


@app.route("/api/scholarships", methods=["GET"])
def get_scholarships():
    """
    Get all scholarships with optional filters.
    Query params (all optional):
      - country: Filter by destination country
      - coverage_type: Filter by coverage type (full_funding, full_tuition, partial_tuition, stipend_only)
      - eligibility_nationality: Filter by eligible nationality ('Pakistan', 'any')
      - gre_required: Filter by GRE requirement (not_required, optional, required)
      - competitiveness: Filter by competitiveness level
      - deadline_before: Filter by deadline before date (YYYY-MM-DD)
      - min_amount: Minimum scholarship amount in USD
    """
    from query_builder import QueryBuilder
    from datetime import datetime

    min_amount, error = validate_optional_int(request.args, "min_amount")
    if error:
        return error

    qb = QueryBuilder("SELECT * FROM scholarships")
    qb.add_filter("country = ?", request.args.get("country"))
    qb.add_filter("coverage_type = ?", request.args.get("coverage_type"))
    qb.add_filter("eligibility_nationality = ?", request.args.get("eligibility_nationality"))
    qb.add_filter("eligibility_gre_required = ?", request.args.get("gre_required"))
    qb.add_filter("competitiveness = ?", request.args.get("competitiveness"))
    qb.add_filter("deadline_date <= ?", request.args.get("deadline_before"))
    qb.add_filter("amount_usd >= ?", min_amount)
    qb.order_by("deadline_date ASC, relevance_score DESC")

    query, params = qb.build()

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        rows = cursor.fetchall()
        scholarships = [dict(row) for row in rows]

    return jsonify({"count": len(scholarships), "scholarships": scholarships})


@app.route("/api/scholarships/urgent", methods=["GET"])
def get_urgent_scholarships():
    """
    Get scholarships with deadlines in the next N days.
    Query params:
      - days: Number of days ahead to look (default: 60)
    """
    from datetime import datetime, timedelta

    days, error = validate_optional_int(request.args, "days")
    if error:
        return error
    days = days or 60

    deadline_cutoff = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d")

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT *,
                   julianday(deadline_date) - julianday('now') as days_remaining
            FROM scholarships
            WHERE deadline_date IS NOT NULL
              AND deadline_date >= date('now')
              AND deadline_date <= ?
            ORDER BY deadline_date ASC
        """, (deadline_cutoff,))
        rows = cursor.fetchall()
        scholarships = [dict(row) for row in rows]

    # Add urgency labels
    for s in scholarships:
        days_left = s.get("days_remaining", 999)
        if days_left <= 7:
            s["urgency"] = "critical"
        elif days_left <= 30:
            s["urgency"] = "urgent"
        else:
            s["urgency"] = "upcoming"

    return jsonify({
        "count": len(scholarships),
        "deadline_cutoff": deadline_cutoff,
        "days_ahead": days,
        "scholarships": scholarships
    })


@app.route("/api/programs/<int:program_id>/scholarships", methods=["GET"])
def get_program_scholarships(program_id):
    """
    Get scholarships applicable to a specific program.
    Returns scholarships linked to this program or its university,
    plus country-wide scholarships for the program's destination.
    """
    with get_db() as conn:
        cursor = conn.cursor()

        # Get program info
        cursor.execute("""
            SELECT p.id, u.id as university_id, u.country
            FROM programs p
            JOIN universities u ON p.university_id = u.id
            WHERE p.id = ?
        """, (program_id,))
        program = cursor.fetchone()

        if not program:
            return jsonify({"error": "Program not found"}), 404

        uni_id = program["university_id"]
        country = program["country"]

        # Get directly linked scholarships
        cursor.execute("""
            SELECT s.*, spl.applicability_notes
            FROM scholarships s
            JOIN scholarship_program_links spl ON s.id = spl.scholarship_id
            WHERE spl.program_id = ? OR spl.university_id = ?
        """, (program_id, uni_id))
        linked = [dict(row) for row in cursor.fetchall()]

        # Get country-wide scholarships
        cursor.execute("""
            SELECT *
            FROM scholarships
            WHERE country = ? OR country = 'any' OR country = 'Europe'
        """, (country,))
        country_wide = [dict(row) for row in cursor.fetchall()]

        # Merge and deduplicate
        seen_ids = {s["id"] for s in linked}
        for s in country_wide:
            if s["id"] not in seen_ids:
                s["applicability_notes"] = f"Country-wide: {s['country']}"
                linked.append(s)
                seen_ids.add(s["id"])

        # Sort by relevance and deadline
        linked.sort(key=lambda x: (-x.get("relevance_score", 0), x.get("deadline_date", "9999")))

    return jsonify({
        "program_id": program_id,
        "country": country,
        "count": len(linked),
        "scholarships": linked
    })


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

    # Validate parameters
    params, error = validate_params(request.args, [LIFESTYLE, FAMILY_YEAR_CAREER, NODE_TYPE, CAREER_SORT])
    if error:
        return error

    limit, error = validate_optional_int(request.args, "limit")
    if error:
        return error

    # Parse leaf_only
    leaf_only = request.args.get("leaf_only", "true").lower() != "false"

    data = calculate_all_career_paths(
        node_type=params["node_type"],
        leaf_only=leaf_only,
        lifestyle=params["lifestyle"],
        family_transition_year=params["family_year"],
    )

    # Sort
    results = data["results"]
    sort_map = {
        "net_benefit": "net_benefit_k",
        "y1": "y1_income_k",
        "y10": "y10_income_k",
        "networth": "path_networth_k",
    }
    key = sort_map.get(params["sort_by"], "net_benefit_k")
    results.sort(key=lambda x: x.get(key, 0), reverse=True)

    # Limit
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

    # Validate parameters
    params, error = validate_params(request.args, [LIFESTYLE, FAMILY_YEAR_CAREER])
    if error:
        return error

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
        lifestyle=params["lifestyle"],
        family_transition_year=params["family_year"],
    )
    result = calculate_career_node_networth(
        node,
        baseline["total_networth_k"],
        lifestyle=params["lifestyle"],
        family_transition_year=params["family_year"],
    )
    result["baseline"] = baseline

    return jsonify(result)


# ═══════════════════════════════════════════════════════════════════════════
# Pakistan Return-to-Work Endpoints
# ═══════════════════════════════════════════════════════════════════════════


@app.route("/api/pakistan/salary-tiers", methods=["GET"])
def get_pakistan_salary_tiers():
    """
    Get Pakistan salary data by employer tier, field, and degree level.
    Query params (all optional):
      - employer_tier: Filter by tier (tier1_multinational, tier2_tech_company, etc.)
      - field: Filter by field (AI/ML, CS/SWE, etc.)
      - degree_level: Filter by degree (bachelors, masters_local, masters_abroad, masters_abroad_exp)
      - city: Filter by city (Karachi, Lahore, Islamabad)
    """
    from query_builder import QueryBuilder

    qb = QueryBuilder("SELECT * FROM pakistan_job_market")
    qb.add_filter("employer_tier = ?", request.args.get("employer_tier"))
    qb.add_filter("field = ?", request.args.get("field"))
    qb.add_filter("degree_level = ?", request.args.get("degree_level"))
    qb.add_filter("city = ?", request.args.get("city"))
    qb.order_by("employer_tier, field, degree_level")

    query, params = qb.build()

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        rows = cursor.fetchall()
        salaries = [dict(row) for row in rows]

    # Also return tier descriptions
    from pakistan_return_calculator import get_all_employer_tiers
    tiers = get_all_employer_tiers()

    return jsonify({
        "count": len(salaries),
        "salaries": salaries,
        "employer_tiers": tiers,
    })


@app.route("/api/networth/<int:program_id>/pakistan-return", methods=["GET"])
def get_pakistan_return_networth(program_id):
    """
    Calculate ROI for: Study abroad → Return to Pakistan.

    Query params:
      - employer_tier: Pakistan employer tier (default: tier2_tech_company)
      - return_after_years: Years abroad before returning (default: 2)
      - lifestyle: 'frugal' or 'comfortable' (default: frugal)
      - family_year: Family transition year 1-13 (default: 5)
    """
    from pakistan_return_calculator import calculate_pakistan_return_networth
    from validators import ParamValidator

    # Validate employer_tier
    tier_validator = ParamValidator(
        name="employer_tier",
        param_type=str,
        default="tier2_tech_company",
        valid_values={
            "tier1_multinational", "tier2_tech_company", "tier3_startup_scale",
            "tier4_local_sme", "consulting_finance", "remote_foreign"
        },
    )
    params, error = validate_params(request.args, [LIFESTYLE, FAMILY_YEAR_MASTERS, tier_validator])
    if error:
        return error

    return_years, error = validate_optional_int(request.args, "return_after_years")
    if error:
        return error
    return_years = return_years if return_years is not None else 2

    # Validate return_after_years
    if return_years < 0 or return_years > 10:
        return jsonify({"error": "return_after_years must be between 0 and 10"}), 400

    # Get program
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT
                p.id, p.program_name, p.field, p.tuition_usd,
                p.y1_salary_usd, p.y5_salary_usd, p.y10_salary_usd,
                p.funding_tier, p.duration_years, p.primary_market,
                u.name as university_name, u.country
            FROM programs p
            JOIN universities u ON p.university_id = u.id
            WHERE p.id = ?
        """, (program_id,))
        row = cursor.fetchone()

    if not row:
        return jsonify({"error": "Program not found"}), 404

    program = dict(row)
    result = calculate_pakistan_return_networth(
        program,
        employer_tier=params["employer_tier"],
        return_after_years=return_years,
        lifestyle=params["lifestyle"],
        family_transition_year=params["family_year"] or 5,
    )

    return jsonify(result)


@app.route("/api/compare/abroad-vs-return/<int:program_id>", methods=["GET"])
def compare_abroad_vs_return(program_id):
    """
    Side-by-side comparison: Stay abroad vs Return to Pakistan.
    Shows multiple return scenarios (0, 2, 5, 10 years abroad).

    Query params:
      - employer_tier: Pakistan employer tier (default: tier2_tech_company)
      - lifestyle: 'frugal' or 'comfortable' (default: frugal)
      - family_year: Family transition year 1-13 (default: 5)
    """
    from pakistan_return_calculator import compare_abroad_vs_return as _compare
    from validators import ParamValidator

    tier_validator = ParamValidator(
        name="employer_tier",
        param_type=str,
        default="tier2_tech_company",
        valid_values={
            "tier1_multinational", "tier2_tech_company", "tier3_startup_scale",
            "tier4_local_sme", "consulting_finance", "remote_foreign"
        },
    )
    params, error = validate_params(request.args, [LIFESTYLE, FAMILY_YEAR_MASTERS, tier_validator])
    if error:
        return error

    # Get program
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT
                p.id, p.program_name, p.field, p.tuition_usd,
                p.y1_salary_usd, p.y5_salary_usd, p.y10_salary_usd,
                p.funding_tier, p.duration_years, p.primary_market,
                u.name as university_name, u.country
            FROM programs p
            JOIN universities u ON p.university_id = u.id
            WHERE p.id = ?
        """, (program_id,))
        row = cursor.fetchone()

    if not row:
        return jsonify({"error": "Program not found"}), 404

    program = dict(row)
    result = _compare(
        program,
        employer_tier=params["employer_tier"],
        lifestyle=params["lifestyle"],
        family_transition_year=params["family_year"] or 5,
    )

    return jsonify(result)


# ═══════════════════════════════════════════════════════════════════════════
# Post-Masters Career Path Endpoints
# ═══════════════════════════════════════════════════════════════════════════


@app.route("/api/ecosystems", methods=["GET"])
def get_ecosystems():
    """
    Get all location ecosystems or filter by country.
    Query params (all optional):
      - country: Filter by country
      - min_startup_strength: Minimum startup ecosystem strength (e.g., 1.0)
      - has_entrepreneur_visa: If "true", only cities with entrepreneur visa paths
    """
    from location_ecosystem import list_ecosystems

    min_strength = None
    if request.args.get("min_startup_strength"):
        try:
            min_strength = float(request.args.get("min_startup_strength"))
        except ValueError:
            return jsonify({"error": "min_startup_strength must be a number"}), 400

    has_visa = None
    if request.args.get("has_entrepreneur_visa"):
        has_visa = request.args.get("has_entrepreneur_visa").lower() == "true"

    ecosystems = list_ecosystems(
        country=request.args.get("country"),
        min_startup_strength=min_strength,
        has_entrepreneur_visa=has_visa,
    )

    return jsonify({
        "count": len(ecosystems),
        "ecosystems": [
            {
                "city": e.city,
                "country": e.country,
                "startup_ecosystem_strength": e.startup_ecosystem_strength,
                "vc_density": e.vc_density,
                "startup_salary_discount": e.startup_salary_discount,
                "equity_multiple_median": e.equity_multiple_median,
                "bigtech_presence": e.bigtech_presence,
                "bigtech_salary_premium": e.bigtech_salary_premium,
                "remote_arbitrage_factor": e.remote_arbitrage_factor,
                "entrepreneur_visa_available": e.entrepreneur_visa_available,
                "entrepreneur_visa_type": e.entrepreneur_visa_type,
                "tech_talent_density": e.tech_talent_density,
                "notes": e.notes,
            }
            for e in ecosystems
        ],
    })


@app.route("/api/ecosystems/<city>", methods=["GET"])
def get_ecosystem_by_city(city):
    """
    Get ecosystem data for a specific city.
    Query param:
      - country: Optional country to disambiguate (e.g., Sydney in Australia vs Canada)
    """
    from location_ecosystem import get_ecosystem

    country = request.args.get("country")
    ecosystem = get_ecosystem(city, country)

    if ecosystem.city == "Unknown":
        return jsonify({"error": f"Ecosystem not found for city: {city}"}), 404

    return jsonify({
        "city": ecosystem.city,
        "country": ecosystem.country,
        "startup_ecosystem_strength": ecosystem.startup_ecosystem_strength,
        "vc_density": ecosystem.vc_density,
        "startup_salary_discount": ecosystem.startup_salary_discount,
        "equity_multiple_median": ecosystem.equity_multiple_median,
        "bigtech_presence": ecosystem.bigtech_presence,
        "bigtech_salary_premium": ecosystem.bigtech_salary_premium,
        "remote_arbitrage_factor": ecosystem.remote_arbitrage_factor,
        "entrepreneur_visa_available": ecosystem.entrepreneur_visa_available,
        "entrepreneur_visa_type": ecosystem.entrepreneur_visa_type,
        "tech_talent_density": ecosystem.tech_talent_density,
        "notes": ecosystem.notes,
    })


@app.route("/api/postmasters/nodes", methods=["GET"])
def get_postmasters_nodes():
    """
    Get all post-masters career nodes.
    Query params (all optional):
      - node_type: Filter by type (employment, startup, remote, return, terminal)
      - phase: Filter by phase (0-3)
    """
    import json as json_module

    with get_db() as conn:
        cursor = conn.cursor()

        query = "SELECT * FROM postmasters_nodes WHERE 1=1"
        params = []

        if request.args.get("node_type"):
            query += " AND node_type = ?"
            params.append(request.args.get("node_type"))

        if request.args.get("phase"):
            query += " AND phase = ?"
            params.append(int(request.args.get("phase")))

        query += " ORDER BY phase, id"
        cursor.execute(query, params)
        rows = cursor.fetchall()

        nodes = []
        for row in rows:
            node = dict(row)
            node["children"] = json_module.loads(node.get("children") or "[]")
            nodes.append(node)

    return jsonify({"count": len(nodes), "nodes": nodes})


@app.route("/api/postmasters/edges", methods=["GET"])
def get_postmasters_edges():
    """
    Get all post-masters edges with optional calibration.
    Query params:
      - source_id: Filter by source node
      - calibrated: If "true", apply profile + ecosystem calibration
      - city: City for ecosystem-based calibration (required if calibrated=true)
    """
    with get_db() as conn:
        cursor = conn.cursor()

        if request.args.get("calibrated", "").lower() == "true":
            from profile_calibrator import calibrate_postmasters_edges, get_profile
            from location_ecosystem import get_ecosystem

            city = request.args.get("city")
            ecosystem = get_ecosystem(city) if city else None

            profile = get_profile(conn)
            edges = calibrate_postmasters_edges(
                profile=profile, ecosystem=ecosystem, conn=conn
            )

            if request.args.get("source_id"):
                edges = [e for e in edges if e["source_id"] == request.args.get("source_id")]

            return jsonify({
                "count": len(edges),
                "edges": edges,
                "calibrated": True,
                "ecosystem_city": city,
            })

        query = "SELECT * FROM postmasters_edges WHERE 1=1"
        params = []

        if request.args.get("source_id"):
            query += " AND source_id = ?"
            params.append(request.args.get("source_id"))

        query += " ORDER BY source_id, target_id"
        cursor.execute(query, params)
        rows = cursor.fetchall()
        edges = [dict(row) for row in rows]

    return jsonify({"count": len(edges), "edges": edges})


@app.route("/api/programs/<int:program_id>/postmasters", methods=["GET"])
def get_program_postmasters_paths(program_id):
    """
    Get post-masters career paths for a program with location-calibrated probabilities.

    This returns the full post-masters decision tree with probabilities adjusted
    for the program's work location ecosystem.

    Query params:
      - calibrated: If "true", apply profile + location calibration (default: true)
    """
    import json as json_module
    from location_ecosystem import get_ecosystem, get_ecosystem_by_country
    from market_mapping import get_market_info
    from profile_calibrator import calibrate_postmasters_edges, get_profile

    with get_db() as conn:
        cursor = conn.cursor()

        # Get program
        cursor.execute("""
            SELECT
                p.id, p.program_name, p.primary_market,
                u.name as university_name, u.country
            FROM programs p
            JOIN universities u ON p.university_id = u.id
            WHERE p.id = ?
        """, (program_id,))
        row = cursor.fetchone()

        if not row:
            return jsonify({"error": "Program not found"}), 404

        program = dict(row)

        # Determine ecosystem
        primary_market = program.get("primary_market") or ""
        uni_country = program.get("country") or "USA"
        market_info = get_market_info(primary_market, uni_country)

        ecosystem = get_ecosystem(market_info.work_city, market_info.work_country)
        if ecosystem is None or ecosystem.city == "Unknown":
            ecosystem = get_ecosystem_by_country(market_info.work_country)

        # Get all nodes
        cursor.execute("SELECT * FROM postmasters_nodes ORDER BY phase, id")
        node_rows = cursor.fetchall()
        nodes = []
        for nr in node_rows:
            node = dict(nr)
            node["children"] = json_module.loads(node.get("children") or "[]")
            nodes.append(node)

        # Get calibrated edges if requested
        calibrated = request.args.get("calibrated", "true").lower() != "false"
        if calibrated:
            profile = get_profile(conn)
            edges = calibrate_postmasters_edges(
                profile=profile, ecosystem=ecosystem, conn=conn
            )
        else:
            cursor.execute("SELECT * FROM postmasters_edges ORDER BY source_id, target_id")
            edge_rows = cursor.fetchall()
            edges = [dict(er) for er in edge_rows]
            for e in edges:
                e["calibrated_probability"] = e["base_probability"]

    return jsonify({
        "program_id": program_id,
        "program_name": program["program_name"],
        "university": program["university_name"],
        "work_city": market_info.work_city,
        "work_country": market_info.work_country,
        "ecosystem": {
            "city": ecosystem.city if ecosystem else None,
            "startup_ecosystem_strength": ecosystem.startup_ecosystem_strength if ecosystem else 1.0,
            "bigtech_presence": ecosystem.bigtech_presence if ecosystem else "none",
            "vc_density": ecosystem.vc_density if ecosystem else "low",
            "entrepreneur_visa_available": ecosystem.entrepreneur_visa_available if ecosystem else False,
        },
        "calibrated": calibrated,
        "nodes": nodes,
        "edges": edges,
    })


@app.route("/api/networth/<int:program_id>/path/<path:path_id>", methods=["GET"])
def get_path_networth(program_id, path_id):
    """
    Calculate 12-year net worth for a specific post-masters career path.

    path_id: Comma-separated node IDs representing the path
      e.g., "pm_bigtech,pm_bigtech_senior,pm_bigtech_staff"

    Query params:
      - lifestyle: "frugal" or "comfortable" (default: frugal)
      - family_year: Calendar year for family transition (default: 5)
      - aid_scenario: "no_aid", "expected", or "best_case" (default: no_aid)
    """
    from postmasters_calculator import calculate_postmasters_path_networth
    from location_ecosystem import get_ecosystem, get_ecosystem_by_country
    from market_mapping import get_market_info

    # Parse path from URL
    path = [p.strip() for p in path_id.split(",") if p.strip()]
    if not path:
        return jsonify({"error": "path_id must be comma-separated node IDs"}), 400

    # Validate params
    params, error = validate_params(
        request.args,
        [LIFESTYLE, FAMILY_YEAR_MASTERS, AID_SCENARIO],
    )
    if error:
        return error

    # Get program
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT
                p.id, p.program_name, p.tuition_usd,
                p.y1_salary_usd, p.y5_salary_usd, p.y10_salary_usd,
                p.duration_years, p.primary_market,
                p.expected_aid_usd, p.best_case_aid_usd, p.coop_earnings_usd,
                p.aid_type,
                u.name as university_name, u.country
            FROM programs p
            JOIN universities u ON p.university_id = u.id
            WHERE p.id = ?
        """, (program_id,))
        row = cursor.fetchone()

    if not row:
        return jsonify({"error": "Program not found"}), 404

    program = dict(row)

    # Get ecosystem
    primary_market = program.get("primary_market") or ""
    uni_country = program.get("country") or "USA"
    market_info = get_market_info(primary_market, uni_country)

    ecosystem = get_ecosystem(market_info.work_city, market_info.work_country)
    if ecosystem is None or ecosystem.city == "Unknown":
        ecosystem = get_ecosystem_by_country(market_info.work_country)

    result = calculate_postmasters_path_networth(
        program=program,
        path=path,
        ecosystem=ecosystem,
        lifestyle=params["lifestyle"],
        family_year=params["family_year"] or 5,
        aid_scenario=params["aid_scenario"],
    )

    result["program_id"] = program_id
    result["program_name"] = program["program_name"]
    result["university"] = program["university_name"]

    return jsonify(result)


@app.route("/api/networth/<int:program_id>/expected", methods=["GET"])
def get_expected_networth(program_id):
    """
    Calculate probability-weighted expected net worth across all post-masters paths.

    Returns expected value plus distribution (p10, p25, p50, p75, p90) and
    the top contributing paths.

    Query params:
      - lifestyle: "frugal" or "comfortable" (default: frugal)
      - family_year: Calendar year for family transition (default: 5)
      - aid_scenario: "no_aid", "expected", or "best_case" (default: no_aid)
    """
    from postmasters_calculator import calculate_expected_networth
    from location_ecosystem import get_ecosystem, get_ecosystem_by_country
    from market_mapping import get_market_info

    # Validate params
    params, error = validate_params(
        request.args,
        [LIFESTYLE, FAMILY_YEAR_MASTERS, AID_SCENARIO],
    )
    if error:
        return error

    # Get program
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT
                p.id, p.program_name, p.tuition_usd,
                p.y1_salary_usd, p.y5_salary_usd, p.y10_salary_usd,
                p.duration_years, p.primary_market,
                p.expected_aid_usd, p.best_case_aid_usd, p.coop_earnings_usd,
                p.aid_type,
                u.name as university_name, u.country
            FROM programs p
            JOIN universities u ON p.university_id = u.id
            WHERE p.id = ?
        """, (program_id,))
        row = cursor.fetchone()

    if not row:
        return jsonify({"error": "Program not found"}), 404

    program = dict(row)

    # Get ecosystem
    primary_market = program.get("primary_market") or ""
    uni_country = program.get("country") or "USA"
    market_info = get_market_info(primary_market, uni_country)

    ecosystem = get_ecosystem(market_info.work_city, market_info.work_country)
    if ecosystem is None or ecosystem.city == "Unknown":
        ecosystem = get_ecosystem_by_country(market_info.work_country)

    result = calculate_expected_networth(
        program=program,
        ecosystem=ecosystem,
        lifestyle=params["lifestyle"],
        family_year=params["family_year"] or 5,
        aid_scenario=params["aid_scenario"],
    )

    result["program_name"] = program["program_name"]
    result["university"] = program["university_name"]

    return jsonify(result)


@app.route("/api/programs/<int:program_id>/ecosystem-comparison", methods=["GET"])
def get_program_ecosystem_comparison(program_id):
    """
    Compare expected net worth for a program across different work ecosystems.

    Shows how outcomes vary depending on where you work after graduation
    (e.g., SF vs NYC vs London vs returning to Pakistan).

    Query params:
      - lifestyle: "frugal" or "comfortable" (default: frugal)
      - cities: Comma-separated list of cities to compare (optional, uses defaults)
    """
    from postmasters_calculator import compare_program_ecosystems

    # Get program
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT
                p.id, p.program_name, p.tuition_usd,
                p.y1_salary_usd, p.y5_salary_usd, p.y10_salary_usd,
                p.duration_years, p.primary_market,
                p.expected_aid_usd, p.best_case_aid_usd, p.coop_earnings_usd,
                p.aid_type,
                u.name as university_name, u.country
            FROM programs p
            JOIN universities u ON p.university_id = u.id
            WHERE p.id = ?
        """, (program_id,))
        row = cursor.fetchone()

    if not row:
        return jsonify({"error": "Program not found"}), 404

    program = dict(row)

    lifestyle = request.args.get("lifestyle", "frugal")
    if lifestyle not in ("frugal", "comfortable"):
        return jsonify({"error": "lifestyle must be 'frugal' or 'comfortable'"}), 400

    cities = None
    if request.args.get("cities"):
        cities = [c.strip() for c in request.args.get("cities").split(",") if c.strip()]

    results = compare_program_ecosystems(
        program=program,
        cities=cities,
        lifestyle=lifestyle,
    )

    return jsonify({
        "program_id": program_id,
        "program_name": program["program_name"],
        "university": program["university_name"],
        "lifestyle": lifestyle,
        "comparisons": results,
    })


if __name__ == "__main__":
    print("🚀 Starting Career Tree API...")
    print("📍 API will be available at: http://localhost:5000")
    print("\n📚 Core Endpoints:")
    print("   GET  /api/health")
    print("   GET  /api/programs")
    print("   GET  /api/programs?gre_required=not_required,waivable&ielts_max=7.0")
    print("   GET  /api/programs/<id>")
    print("   GET  /api/programs/<id>/full  (with visa, QoL, immigration data)")
    print("   GET  /api/programs/<id>/scholarships  (applicable scholarships)")
    print("   GET  /api/universities")
    print("   GET  /api/stats")
    print("   GET  /api/search?q=<query>")
    print("\n💰 Net Worth & Financial:")
    print("   GET  /api/networth")
    print("   GET  /api/networth?aid_scenario=expected&field=AI/ML&compact=true")
    print("   GET  /api/networth/<program_id>")
    print("   GET  /api/networth/<program_id>/compare  (all 3 aid scenarios)")
    print("   GET  /api/networth/<program_id>/pakistan-return?return_after_years=2")
    print("   GET  /api/compare/abroad-vs-return/<program_id>")
    print("   GET  /api/affordability")
    print("   GET  /api/networth/career")
    print("   GET  /api/networth/career/<node_id>")
    print("\n🎓 Scholarships:")
    print("   GET  /api/scholarships")
    print("   GET  /api/scholarships?coverage_type=full_funding&gre_required=not_required")
    print("   GET  /api/scholarships/urgent  (deadlines in next 60 days)")
    print("\n🇵🇰 Pakistan Return Model:")
    print("   GET  /api/pakistan/salary-tiers")
    print("   GET  /api/pakistan/salary-tiers?employer_tier=tier1_multinational")
    print("\n🛂 Visa & Immigration:")
    print("   GET  /api/visa-rates")
    print("   GET  /api/visa-rates/<country>/<nationality>")
    print("   GET  /api/immigration/<country>")
    print("   GET  /api/immigration")
    print("\n🌍 Quality of Life:")
    print("   GET  /api/qol/<city>")
    print("   GET  /api/qol")
    print("   GET  /api/industry-hubs/<city>")
    print("   GET  /api/industry-hubs")
    print("\n👤 Profile & Calibration:")
    print("   GET  /api/profile")
    print("   PUT  /api/profile")
    print("   GET  /api/calibration-summary")
    print("   GET  /api/edges?calibrated=true")
    print("\n🔗 Test: http://localhost:5000/api/scholarships/urgent\n")

    app.run(debug=True, host="0.0.0.0", port=5000)
