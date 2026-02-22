"""
Flask API for Career Decision Tree
Serves program data from SQLite database
"""

from flask import Flask, jsonify, request
from flask_cors import CORS
import sqlite3
import json
from pathlib import Path

app = Flask(__name__)
CORS(app)  # Enable CORS for React frontend

DB_PATH = Path(__file__).parent / "career_tree.db"


def get_db():
    """Get database connection"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # Return rows as dictionaries
    return conn


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
    conn = get_db()
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

    if request.args.get("max_tuition"):
        query += " AND p.tuition_usd <= ?"
        params.append(int(request.args.get("max_tuition")))

    if request.args.get("min_y10_salary"):
        query += " AND p.y10_salary_usd >= ?"
        params.append(int(request.args.get("min_y10_salary")))

    # Execute query
    cursor.execute(query, params)
    rows = cursor.fetchall()

    # Convert to list of dicts
    programs = [dict(row) for row in rows]

    conn.close()

    return jsonify({"count": len(programs), "programs": programs})


@app.route("/api/programs/<int:program_id>", methods=["GET"])
def get_program(program_id):
    """Get a specific program by ID"""
    conn = get_db()
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
    conn.close()

    if row:
        return jsonify(dict(row))
    else:
        return jsonify({"error": "Program not found"}), 404


@app.route("/api/universities", methods=["GET"])
def get_universities():
    """Get all universities with program counts"""
    conn = get_db()
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

    conn.close()

    return jsonify({"count": len(universities), "universities": universities})


@app.route("/api/stats", methods=["GET"])
def get_stats():
    """Get summary statistics"""
    conn = get_db()
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

    conn.close()

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
    conn = get_db()
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

    conn.close()

    return jsonify({"count": len(nodes), "nodes": nodes})


@app.route("/api/career-nodes/<string:node_id>", methods=["GET"])
def get_career_node(node_id):
    """Get a specific career node by ID"""
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM career_nodes WHERE id = ?", (node_id,))
    row = cursor.fetchone()
    conn.close()

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
    conn = get_db()
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

        conn.close()
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
        query += " AND e.source_id IN (SELECT id FROM career_nodes WHERE node_type = ?)"
        params.append(request.args.get("node_type"))

    query += " ORDER BY e.source_id, e.target_id"
    cursor.execute(query, params)
    rows = cursor.fetchall()

    edges = [dict(row) for row in rows]

    conn.close()

    return jsonify({"count": len(edges), "edges": edges})


@app.route("/api/profile", methods=["GET"])
def get_profile():
    """
    Get the current user profile used for probability calibration.
    Returns all 13 profile factors with their current values.
    """
    from profile_calibrator import get_profile as _get_profile

    conn = get_db()
    profile = _get_profile(conn)
    conn.close()

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

    conn = get_db()

    try:
        # Load current profile, merge with updates
        current = _get_profile(conn)
        current.update(data)
        saved = save_profile(current, conn)
    except ValueError as e:
        conn.close()
        return jsonify({"error": str(e)}), 400

    conn.close()

    return jsonify({"profile": saved, "message": "Profile updated"})


@app.route("/api/calibration-summary", methods=["GET"])
def get_calibration_summary():
    """
    Get a summary of how the current profile affects edge probabilities.
    Shows which edges changed and by how much.
    """
    from profile_calibrator import get_calibration_summary as _get_summary

    conn = get_db()
    summary = _get_summary(conn=conn)
    conn.close()

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

    conn = get_db()
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
        (f"%{query_text}%", f"%{query_text}%", f"%{query_text}%", f"%{query_text}%"),
    )

    rows = cursor.fetchall()
    results = [dict(row) for row in rows]

    conn.close()

    return jsonify({"query": query_text, "count": len(results), "results": results})


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
      - sort_by: Sort field — net_benefit, cost, y1, y10, networth (default: net_benefit)
      - field: Filter by field (AI/ML, CS/SWE, etc.)
      - funding_tier: Filter by tier
      - work_country: Filter by work country
      - limit: Max results (default: all)
      - compact: If "true", omit yearly breakdowns (default: false)
    """
    from networth_calculator import calculate_all_programs

    # Parse optional baseline overrides from query params
    baseline_salary = None
    baseline_growth = None
    if request.args.get("baseline_salary"):
        baseline_salary = float(request.args.get("baseline_salary"))
    if request.args.get("baseline_growth"):
        baseline_growth = float(request.args.get("baseline_growth"))

    # Parse lifestyle tier
    lifestyle = request.args.get("lifestyle", "frugal")
    if lifestyle not in ("frugal", "comfortable"):
        return jsonify({"error": "lifestyle must be 'frugal' or 'comfortable'"}), 400

    # Parse family transition year
    family_transition_year = None
    if request.args.get("family_year"):
        try:
            family_transition_year = int(request.args.get("family_year"))
            if not (1 <= family_transition_year <= 13):
                return jsonify(
                    {"error": "family_year must be between 1 and 13 (13 = never)"}
                ), 400
        except (ValueError, TypeError):
            return jsonify(
                {"error": "family_year must be an integer between 1 and 13"}
            ), 400

    data = calculate_all_programs(
        baseline_salary=baseline_salary,
        baseline_growth=baseline_growth,
        lifestyle=lifestyle,
        family_transition_year=family_transition_year,
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

    # Sort
    sort_key = request.args.get("sort_by", "net_benefit")
    sort_map = {
        "net_benefit": "net_benefit_k",
        "cost": "total_study_cost_k",
        "y1": "y1_salary_k",
        "y10": "y10_salary_k",
        "networth": "masters_networth_k",
    }
    key = sort_map.get(sort_key, "net_benefit_k")
    programs.sort(key=lambda x: x.get(key, 0), reverse=(sort_key != "cost"))

    # Limit
    if request.args.get("limit"):
        programs = programs[: int(request.args.get("limit"))]

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
    """
    from networth_calculator import (
        calculate_program_networth,
        calculate_baseline_networth,
    )

    # Parse lifestyle tier
    lifestyle = request.args.get("lifestyle", "frugal")
    if lifestyle not in ("frugal", "comfortable"):
        return jsonify({"error": "lifestyle must be 'frugal' or 'comfortable'"}), 400

    # Parse family transition year
    family_transition_year = None
    if request.args.get("family_year"):
        try:
            family_transition_year = int(request.args.get("family_year"))
            if not (1 <= family_transition_year <= 13):
                return jsonify(
                    {"error": "family_year must be between 1 and 13 (13 = never)"}
                ), 400
        except (ValueError, TypeError):
            return jsonify(
                {"error": "family_year must be an integer between 1 and 13"}
            ), 400

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT
            p.id, p.program_name, p.field, p.tuition_usd,
            p.y1_salary_usd, p.y5_salary_usd, p.y10_salary_usd,
            p.net_10yr_usd, p.funding_tier, p.duration_years,
            p.primary_market, p.notes,
            u.name as university_name, u.country, u.region
        FROM programs p
        JOIN universities u ON p.university_id = u.id
        WHERE p.id = ?
    """,
        (program_id,),
    )

    row = cursor.fetchone()
    conn.close()

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
    )
    result["baseline"] = baseline

    return jsonify(result)


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
    lifestyle = request.args.get("lifestyle", "frugal")
    if lifestyle not in ("frugal", "comfortable"):
        return jsonify({"error": "lifestyle must be 'frugal' or 'comfortable'"}), 400

    # Parse family transition year
    family_transition_year = None
    if request.args.get("family_year"):
        try:
            family_transition_year = int(request.args.get("family_year"))
            if not (1 <= family_transition_year <= 11):
                return jsonify(
                    {"error": "family_year must be between 1 and 11 (11 = never)"}
                ), 400
        except (ValueError, TypeError):
            return jsonify(
                {"error": "family_year must be an integer between 1 and 11"}
            ), 400

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
    if request.args.get("limit"):
        results = results[: int(request.args.get("limit"))]

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
    lifestyle = request.args.get("lifestyle", "frugal")
    if lifestyle not in ("frugal", "comfortable"):
        return jsonify({"error": "lifestyle must be 'frugal' or 'comfortable'"}), 400

    # Parse family transition year
    family_transition_year = None
    if request.args.get("family_year"):
        try:
            family_transition_year = int(request.args.get("family_year"))
            if not (1 <= family_transition_year <= 11):
                return jsonify(
                    {"error": "family_year must be between 1 and 11 (11 = never)"}
                ), 400
        except (ValueError, TypeError):
            return jsonify(
                {"error": "family_year must be an integer between 1 and 11"}
            ), 400

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM career_nodes WHERE id = ?", (node_id,))
    row = cursor.fetchone()
    conn.close()

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
    print("   GET  /api/networth?field=AI/ML&sort_by=net_benefit&compact=true")
    print("   GET  /api/networth/<program_id>")
    print("   GET  /api/networth/career")
    print("   GET  /api/networth/career?node_type=trading&compact=true")
    print("   GET  /api/networth/career/<node_id>")
    print("\n🔗 Test it: http://localhost:5000/api/career-nodes\n")

    app.run(debug=True, host="0.0.0.0", port=5000)
