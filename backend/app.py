"""
Flask API for Career Decision Tree
Serves program data from SQLite database
"""
from flask import Flask, jsonify, request
from flask_cors import CORS
import sqlite3
from pathlib import Path

app = Flask(__name__)
CORS(app)  # Enable CORS for React frontend

DB_PATH = Path(__file__).parent / "career_tree.db"

def get_db():
    """Get database connection"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # Return rows as dictionaries
    return conn

@app.route('/api/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({"status": "ok", "message": "Career Tree API is running"})

@app.route('/api/programs', methods=['GET'])
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
    if request.args.get('field'):
        query += " AND p.field = ?"
        params.append(request.args.get('field'))

    if request.args.get('funding_tier'):
        query += " AND p.funding_tier = ?"
        params.append(request.args.get('funding_tier'))

    if request.args.get('country'):
        query += " AND u.country = ?"
        params.append(request.args.get('country'))

    if request.args.get('max_tuition'):
        query += " AND p.tuition_usd <= ?"
        params.append(int(request.args.get('max_tuition')))

    if request.args.get('min_y10_salary'):
        query += " AND p.y10_salary_usd >= ?"
        params.append(int(request.args.get('min_y10_salary')))

    # Execute query
    cursor.execute(query, params)
    rows = cursor.fetchall()

    # Convert to list of dicts
    programs = [dict(row) for row in rows]

    conn.close()

    return jsonify({
        "count": len(programs),
        "programs": programs
    })

@app.route('/api/programs/<int:program_id>', methods=['GET'])
def get_program(program_id):
    """Get a specific program by ID"""
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            p.*, u.name as university_name, u.country, u.region, u.tier as university_tier
        FROM programs p
        JOIN universities u ON p.university_id = u.id
        WHERE p.id = ?
    """, (program_id,))

    row = cursor.fetchone()
    conn.close()

    if row:
        return jsonify(dict(row))
    else:
        return jsonify({"error": "Program not found"}), 404

@app.route('/api/universities', methods=['GET'])
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

    return jsonify({
        "count": len(universities),
        "universities": universities
    })

@app.route('/api/stats', methods=['GET'])
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
    by_tier = {row['funding_tier']: row['count'] for row in cursor.fetchall()}

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

    return jsonify({
        "total_programs": total_programs,
        "total_universities": total_universities,
        "by_tier": by_tier,
        "by_field": by_field,
        "by_country": by_country,
        "salary_stats": salary_stats
    })

@app.route('/api/search', methods=['GET'])
def search():
    """
    Search programs by keyword
    Query param: q (search query)
    """
    query_text = request.args.get('q', '')

    if not query_text:
        return jsonify({"error": "Query parameter 'q' is required"}), 400

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
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
    """, (f'%{query_text}%', f'%{query_text}%', f'%{query_text}%', f'%{query_text}%'))

    rows = cursor.fetchall()
    results = [dict(row) for row in rows]

    conn.close()

    return jsonify({
        "query": query_text,
        "count": len(results),
        "results": results
    })

if __name__ == '__main__':
    print("🚀 Starting Career Tree API...")
    print("📍 API will be available at: http://localhost:5000")
    print("\n📚 Endpoints:")
    print("   GET  /api/health")
    print("   GET  /api/programs")
    print("   GET  /api/programs/<id>")
    print("   GET  /api/universities")
    print("   GET  /api/stats")
    print("   GET  /api/search?q=<query>")
    print("\n🔗 Test it: http://localhost:5000/api/stats\n")

    app.run(debug=True, host='0.0.0.0', port=5000)
