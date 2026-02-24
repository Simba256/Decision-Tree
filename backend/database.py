"""
Database setup and models for Career Decision Tree
"""

import sqlite3

from config import DB_PATH, get_logger

logger = get_logger(__name__)


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
            expected_aid_pct REAL DEFAULT 0,
            expected_aid_usd INTEGER DEFAULT 0,
            best_case_aid_pct REAL DEFAULT 0,
            best_case_aid_usd INTEGER DEFAULT 0,
            aid_type TEXT DEFAULT 'none',
            coop_earnings_usd INTEGER DEFAULT 0,
            gre_quant_target INTEGER,
            gre_verbal_target INTEGER,
            gre_required TEXT DEFAULT 'not_required',
            initial_capital_usd INTEGER DEFAULT 0,
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
            node_type TEXT DEFAULT 'career',
            income_floor_usd INTEGER,
            income_ceiling_usd INTEGER,
            initial_capital_usd INTEGER,
            ongoing_cost_usd INTEGER,
            y1_income_usd INTEGER,
            y5_income_usd INTEGER,
            y10_income_usd INTEGER
        )
    """)

    # Edges table: parent-child relationships with conditional probabilities
    # link_type: 'child' = normal tree edge, 'transition' = cross-path link,
    #            'enables' = financial enablement, 'fallback' = failure recovery
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS edges (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_id TEXT NOT NULL,
            target_id TEXT NOT NULL,
            probability REAL NOT NULL,
            link_type TEXT NOT NULL DEFAULT 'child',
            note TEXT,
            UNIQUE(source_id, target_id, link_type)
        )
    """)

    # ─── Financial Aid Tables ───────────────────────────────────────────────

    # Scholarships catalog: all known scholarships, grants, fellowships
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS scholarships (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            provider TEXT NOT NULL,
            country TEXT,
            coverage_type TEXT NOT NULL,
            amount_usd INTEGER,
            amount_description TEXT,
            eligibility_nationality TEXT,
            eligibility_min_gpa REAL,
            eligibility_min_work_years REAL,
            eligibility_gre_required TEXT DEFAULT 'not_required',
            eligibility_ielts_min REAL,
            eligibility_notes TEXT,
            competitiveness TEXT,
            annual_awards INTEGER,
            deadline_description TEXT,
            application_url TEXT,
            return_bond_years INTEGER DEFAULT 0,
            relevance_score INTEGER,
            notes TEXT
        )
    """)

    # Program-level aid profiles: per-program financial aid estimates
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS program_aid_profiles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            program_id INTEGER NOT NULL,
            expected_aid_pct REAL DEFAULT 0,
            expected_aid_usd INTEGER DEFAULT 0,
            best_case_aid_pct REAL DEFAULT 0,
            best_case_aid_usd INTEGER DEFAULT 0,
            aid_type TEXT DEFAULT 'none',
            coop_earnings_usd INTEGER DEFAULT 0,
            ta_ra_probability REAL DEFAULT 0,
            ta_ra_annual_stipend_usd INTEGER,
            gre_quant_target INTEGER,
            gre_verbal_target INTEGER,
            gre_required TEXT DEFAULT 'not_required',
            funding_notes TEXT,
            FOREIGN KEY (program_id) REFERENCES programs(id),
            UNIQUE(program_id)
        )
    """)

    # Many-to-many: which scholarships apply to which programs/universities
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS scholarship_program_links (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scholarship_id INTEGER NOT NULL,
            program_id INTEGER,
            university_id INTEGER,
            applicability_notes TEXT,
            FOREIGN KEY (scholarship_id) REFERENCES scholarships(id),
            FOREIGN KEY (program_id) REFERENCES programs(id),
            FOREIGN KEY (university_id) REFERENCES universities(id)
        )
    """)

    # ─── Reference Data Tables ──────────────────────────────────────────────

    # Exchange rates: local currency per 1 USD
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS exchange_rates (
            currency TEXT PRIMARY KEY,
            rate_per_usd REAL NOT NULL,
            country_name TEXT
        )
    """)

    # Tax brackets: progressive income tax brackets per country/scope
    # scope distinguishes federal vs state/provincial vs city brackets
    # threshold_lc is in local currency; use exchange_rates to convert
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tax_brackets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            country TEXT NOT NULL,
            scope TEXT NOT NULL DEFAULT 'federal',
            bracket_order INTEGER NOT NULL,
            threshold_lc REAL NOT NULL,
            rate REAL NOT NULL,
            currency TEXT NOT NULL DEFAULT 'USD',
            UNIQUE(country, scope, bracket_order)
        )
    """)

    # Tax config: key-value pairs for per-country tax parameters
    # Stores deductions, social contribution rates, caps, special flags
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tax_config (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            country TEXT NOT NULL,
            scope TEXT NOT NULL DEFAULT 'federal',
            config_key TEXT NOT NULL,
            config_value REAL NOT NULL,
            description TEXT,
            UNIQUE(country, scope, config_key)
        )
    """)

    # Tax country profiles: consolidated country tax calculation rules
    # This table drives the generic _calculate_country_tax() function
    # Replaces per-country functions with data-driven configuration
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tax_country_profiles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            country TEXT NOT NULL UNIQUE,
            currency TEXT NOT NULL DEFAULT 'USD',
            -- Social contributions
            social_rate REAL DEFAULT 0,
            social_cap_lc REAL,
            -- Surtax on income tax
            surtax_rate REAL DEFAULT 0,
            surtax_threshold_lc REAL,
            -- Personal allowance / standard deduction
            personal_allowance_lc REAL DEFAULT 0,
            pa_taper_start_lc REAL,
            pa_taper_rate REAL DEFAULT 0.5,
            -- Professional expense deduction (France-style)
            professional_deduction_rate REAL DEFAULT 0,
            -- Local/municipal tax
            local_tax_rate REAL DEFAULT 0,
            -- Tax ceiling (Denmark-style cap)
            tax_ceiling REAL,
            -- Cess on income tax (India-style)
            cess_rate REAL DEFAULT 0,
            -- Standard rate cap (Hong Kong-style)
            standard_rate_cap REAL,
            -- Special calculation strategy (for complex cases)
            -- Values: 'standard', 'uk_pa_taper', 'japan_deduction', 'canada_surtax', 'hk_standard_cap'
            calculation_strategy TEXT DEFAULT 'standard',
            -- Notes for documentation
            notes TEXT
        )
    """)

    # Living costs: per-city annual costs for student/single/family
    # Two lifestyle tiers: frugal (default) and comfortable
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS living_costs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            city TEXT NOT NULL UNIQUE,
            student_cost_k REAL NOT NULL,
            single_cost_k REAL NOT NULL,
            family_cost_k REAL NOT NULL,
            comfortable_student_cost_k REAL,
            comfortable_single_cost_k REAL,
            comfortable_family_cost_k REAL
        )
    """)

    # Country-to-default-city mapping for living cost fallbacks
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS country_default_cities (
            country TEXT PRIMARY KEY,
            default_city TEXT NOT NULL
        )
    """)

    # Market mappings: primary_market string -> work location
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS market_mappings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            primary_market TEXT NOT NULL UNIQUE,
            work_country TEXT NOT NULL,
            work_city TEXT NOT NULL,
            us_state TEXT
        )
    """)

    # US region-to-state mapping for dynamic parsing
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS us_region_states (
            region_keyword TEXT PRIMARY KEY,
            state_code TEXT NOT NULL,
            display_city TEXT NOT NULL
        )
    """)

    # User profile for probability calibration
    # Single-row table (id=1). All fields have sensible defaults matching
    # the current hardcoded user (L3 Embedded AI at Motive, Pakistan).
    # The calibration engine applies multipliers based on these values
    # to adjust edge probabilities, then re-normalizes child groups to 1.0.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_profile (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            years_experience REAL NOT NULL DEFAULT 2.0,
            performance_rating TEXT NOT NULL DEFAULT 'strong',
            risk_tolerance TEXT NOT NULL DEFAULT 'moderate',
            available_savings_usd INTEGER NOT NULL DEFAULT 5000,
            english_level TEXT NOT NULL DEFAULT 'professional',
            gpa REAL DEFAULT 3.5,
            gre_score INTEGER,
            ielts_score REAL,
            has_publications INTEGER NOT NULL DEFAULT 0,
            has_freelance_profile INTEGER NOT NULL DEFAULT 0,
            has_side_projects INTEGER NOT NULL DEFAULT 0,
            quant_aptitude TEXT NOT NULL DEFAULT 'moderate',
            current_salary_pkr INTEGER NOT NULL DEFAULT 220000
        )
    """)

    # Insert default profile row if not exists
    cursor.execute("""
        INSERT OR IGNORE INTO user_profile (id) VALUES (1)
    """)

    # ─── Indexes ─────────────────────────────────────────────────────────────

    cursor.execute("CREATE INDEX IF NOT EXISTS idx_programs_field ON programs(field)")
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_programs_funding_tier ON programs(funding_tier)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_programs_country ON programs(university_id)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_universities_country ON universities(country)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_tax_brackets_country ON tax_brackets(country, scope)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_tax_config_country ON tax_config(country)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_tax_country_profiles ON tax_country_profiles(country)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_market_mappings_market ON market_mappings(primary_market)"
    )
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_edges_source ON edges(source_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_edges_target ON edges(target_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_edges_link_type ON edges(link_type)")
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_program_aid_profiles_program ON program_aid_profiles(program_id)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_scholarship_links_scholarship ON scholarship_program_links(scholarship_id)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_scholarship_links_program ON scholarship_program_links(program_id)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_scholarships_country ON scholarships(country)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_scholarships_relevance ON scholarships(relevance_score)"
    )

    conn.commit()
    conn.close()

    logger.info("Database created at: %s", DB_PATH)


if __name__ == "__main__":
    create_database()
