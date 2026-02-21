"""
Database setup and models for Career Decision Tree
"""
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "career_tree.db"

def create_database():
    """Create the database schema"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Universities table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS universities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            country TEXT NOT NULL,
            region TEXT,
            tier TEXT,
            UNIQUE(name, country)
        )
    """)

    # Programs table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS programs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            university_id INTEGER NOT NULL,
            program_name TEXT NOT NULL,
            field TEXT NOT NULL,
            degree_type TEXT,
            tuition_usd INTEGER,
            duration_years REAL DEFAULT 2.0,
            y1_salary_usd INTEGER,
            y5_salary_usd INTEGER,
            y10_salary_usd INTEGER,
            p90_y10_usd INTEGER,
            net_10yr_usd INTEGER,
            acceptance_rate REAL,
            visa_approval_rate REAL,
            funding_tier TEXT,
            primary_market TEXT,
            key_employers TEXT,
            notes TEXT,
            data_confidence TEXT,
            FOREIGN KEY (university_id) REFERENCES universities(id)
        )
    """)

    # Outcomes table (for post-graduation paths)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS outcomes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            program_id INTEGER,
            outcome_type TEXT,
            description TEXT,
            probability REAL,
            y1_salary_usd INTEGER,
            y5_salary_usd INTEGER,
            y10_salary_usd INTEGER,
            notes TEXT,
            FOREIGN KEY (program_id) REFERENCES programs(id)
        )
    """)

    # Career nodes table (for the original career tree)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS career_nodes (
            id TEXT PRIMARY KEY,
            phase INTEGER,
            label TEXT NOT NULL,
            salary TEXT,
            probability REAL,
            color TEXT,
            note TEXT,
            children TEXT,
            node_type TEXT DEFAULT 'career'
        )
    """)

    # Create indexes for faster queries
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_programs_field ON programs(field)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_programs_funding_tier ON programs(funding_tier)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_programs_country ON programs(university_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_universities_country ON universities(country)")

    conn.commit()
    conn.close()

    print(f"✅ Database created at: {DB_PATH}")

if __name__ == "__main__":
    create_database()
