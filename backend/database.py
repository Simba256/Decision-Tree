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
            -- Post-graduation work visa
            visa_type TEXT,
            visa_duration_years REAL,
            work_auth_certainty TEXT,
            -- Program structure
            stem_designation INTEGER DEFAULT 0,
            part_time_available INTEGER DEFAULT 0,
            online_hybrid_option INTEGER DEFAULT 0,
            thesis_required INTEGER DEFAULT 0,
            capstone_project INTEGER DEFAULT 1,
            -- Placement data
            employment_rate_6mo REAL,
            median_time_to_offer_weeks INTEGER,
            career_services_rating REAL,
            -- Class/cohort metrics
            avg_class_size INTEGER,
            international_student_pct REAL,
            pakistan_alumni_network INTEGER DEFAULT 0,
            -- Family considerations
            spouse_work_permit INTEGER DEFAULT 0,
            dependent_visa_cost_usd INTEGER DEFAULT 0,
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

    # ─── Quality of Life & Immigration Tables ────────────────────────────────

    # QoL metrics per city (extends living_costs with non-financial factors)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS qol_metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            city TEXT NOT NULL UNIQUE,
            country TEXT NOT NULL,
            -- Safety & stability
            safety_index REAL,
            political_stability_index REAL,
            -- Climate
            climate_type TEXT,
            avg_winter_temp_c REAL,
            avg_summer_temp_c REAL,
            sunshine_hours_year INTEGER,
            -- Community & lifestyle
            halal_food_availability TEXT,
            muslim_community_size TEXT,
            public_transit_rating REAL,
            healthcare_quality_rating REAL,
            -- Work-life
            avg_commute_minutes INTEGER,
            work_life_balance_index REAL,
            notes TEXT
        )
    """)

    # Immigration policy per country (affecting career decisions)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS immigration_policy (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            country TEXT NOT NULL UNIQUE,
            -- Student visa
            student_visa_work_hours INTEGER,
            student_visa_cost_usd INTEGER,
            -- Post-study work
            post_study_work_visa_name TEXT,
            post_study_work_duration_months INTEGER,
            post_study_work_extensions TEXT,
            -- Work visa / permanent residence
            work_visa_lottery INTEGER DEFAULT 0,
            pr_pathway_years REAL,
            pr_pathway_difficulty TEXT,
            points_based_immigration INTEGER DEFAULT 0,
            -- Family
            spouse_open_work_permit INTEGER DEFAULT 0,
            dependent_included_in_visa INTEGER DEFAULT 1,
            -- Special programs
            startup_visa_available INTEGER DEFAULT 0,
            entrepreneur_pathway TEXT,
            -- Pakistani-specific
            pakistan_visa_processing_weeks INTEGER,
            pakistan_acceptance_rate REAL,
            last_updated DATE,
            notes TEXT
        )
    """)

    # Industry hubs per city (tech/industry presence for career opportunities)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS industry_hubs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            city TEXT NOT NULL,
            industry TEXT NOT NULL,
            hub_strength TEXT,
            major_employers TEXT,
            avg_tech_salary_usd INTEGER,
            job_market_competitiveness TEXT,
            remote_work_prevalence TEXT,
            UNIQUE(city, industry)
        )
    """)

    # Visa approval rates by nationality (Phase 3)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS visa_approval_by_nationality (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            country TEXT NOT NULL,
            nationality TEXT NOT NULL,
            visa_type TEXT NOT NULL,
            approval_rate REAL,
            avg_processing_weeks INTEGER,
            denial_reasons TEXT,
            tips TEXT,
            last_updated DATE,
            UNIQUE(country, nationality, visa_type)
        )
    """)

    # Pakistan job market (Phase 4)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS pakistan_job_market (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employer_tier TEXT NOT NULL,
            field TEXT NOT NULL,
            degree_level TEXT NOT NULL,
            city TEXT NOT NULL,
            y1_salary_pkr INTEGER,
            y5_salary_pkr INTEGER,
            y10_salary_pkr INTEGER,
            annual_growth_rate REAL,
            notes TEXT,
            UNIQUE(employer_tier, field, degree_level, city)
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

    # ─── Post-Masters Career Decision Tables ──────────────────────────────────

    # Location ecosystems: startup/career ecosystem data by city
    # Used to adjust post-masters path probabilities based on location
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS location_ecosystems (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            city TEXT NOT NULL,
            country TEXT NOT NULL,
            -- Startup ecosystem
            startup_ecosystem_strength REAL DEFAULT 1.0,
            vc_density TEXT,
            startup_salary_discount REAL DEFAULT 0.7,
            equity_multiple_median REAL DEFAULT 0.0,
            -- Big tech presence
            bigtech_presence TEXT,
            bigtech_salary_premium REAL DEFAULT 1.0,
            -- Remote work / arbitrage
            remote_arbitrage_factor REAL DEFAULT 1.0,
            -- Entrepreneur visas
            entrepreneur_visa_available INTEGER DEFAULT 0,
            entrepreneur_visa_type TEXT,
            -- Talent density
            tech_talent_density TEXT,
            -- Metadata
            notes TEXT,
            UNIQUE(city, country)
        )
    """)

    # Post-masters career nodes: career paths after completing masters
    # Follows the same pattern as career_nodes but for post-graduation decisions
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS postmasters_nodes (
            id TEXT PRIMARY KEY,
            phase INTEGER NOT NULL,
            node_type TEXT NOT NULL,
            label TEXT NOT NULL,
            -- Income modeling
            salary_multiplier REAL DEFAULT 1.0,
            equity_expected_value_usd INTEGER DEFAULT 0,
            -- Probability and location requirements
            base_probability REAL DEFAULT 0.0,
            requires_location_type TEXT,
            -- Living cost overrides (for remote/return paths)
            living_cost_location TEXT,
            tax_country TEXT,
            -- Metadata
            color TEXT,
            note TEXT,
            children TEXT
        )
    """)

    # Post-masters edges: transitions between post-masters nodes
    # Includes location sensitivity weights for probability adjustment
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS postmasters_edges (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_id TEXT NOT NULL,
            target_id TEXT NOT NULL,
            base_probability REAL NOT NULL,
            -- Location sensitivity (multiplied by ecosystem factor)
            startup_ecosystem_weight REAL DEFAULT 0.0,
            bigtech_presence_weight REAL DEFAULT 0.0,
            -- Link type for visualization
            link_type TEXT NOT NULL DEFAULT 'child',
            note TEXT,
            UNIQUE(source_id, target_id, link_type),
            FOREIGN KEY (source_id) REFERENCES postmasters_nodes(id),
            FOREIGN KEY (target_id) REFERENCES postmasters_nodes(id)
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
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_qol_metrics_city ON qol_metrics(city)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_qol_metrics_country ON qol_metrics(country)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_immigration_policy_country ON immigration_policy(country)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_industry_hubs_city ON industry_hubs(city)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_industry_hubs_industry ON industry_hubs(industry)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_visa_approval_country ON visa_approval_by_nationality(country)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_visa_approval_nationality ON visa_approval_by_nationality(nationality)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_pakistan_job_market_tier ON pakistan_job_market(employer_tier)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_pakistan_job_market_field ON pakistan_job_market(field)"
    )
    # Post-masters tables indexes
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_location_ecosystems_city ON location_ecosystems(city)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_location_ecosystems_country ON location_ecosystems(country)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_postmasters_nodes_phase ON postmasters_nodes(phase)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_postmasters_nodes_type ON postmasters_nodes(node_type)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_postmasters_edges_source ON postmasters_edges(source_id)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_postmasters_edges_target ON postmasters_edges(target_id)"
    )

    conn.commit()
    conn.close()

    logger.info("Database created at: %s", DB_PATH)


def migrate_database():
    """Run database migrations to add new columns to existing tables."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Get existing columns in programs table
    cursor.execute("PRAGMA table_info(programs)")
    existing_cols = {row[1] for row in cursor.fetchall()}

    # New columns to add to programs table
    new_program_columns = [
        ("visa_type", "TEXT"),
        ("visa_duration_years", "REAL"),
        ("work_auth_certainty", "TEXT"),
        ("stem_designation", "INTEGER DEFAULT 0"),
        ("part_time_available", "INTEGER DEFAULT 0"),
        ("online_hybrid_option", "INTEGER DEFAULT 0"),
        ("thesis_required", "INTEGER DEFAULT 0"),
        ("capstone_project", "INTEGER DEFAULT 1"),
        ("employment_rate_6mo", "REAL"),
        ("median_time_to_offer_weeks", "INTEGER"),
        ("career_services_rating", "REAL"),
        ("avg_class_size", "INTEGER"),
        ("international_student_pct", "REAL"),
        ("pakistan_alumni_network", "INTEGER DEFAULT 0"),
        ("spouse_work_permit", "INTEGER DEFAULT 0"),
        ("dependent_visa_cost_usd", "INTEGER DEFAULT 0"),
        # GRE/IELTS requirements (Phase 1)
        ("gre_waiver_conditions", "TEXT"),
        ("ielts_min_score", "REAL"),
        ("toefl_min_score", "INTEGER"),
        ("english_waiver_available", "INTEGER DEFAULT 0"),
    ]

    for col_name, col_type in new_program_columns:
        if col_name not in existing_cols:
            try:
                cursor.execute(f"ALTER TABLE programs ADD COLUMN {col_name} {col_type}")
                logger.info("Added column %s to programs table", col_name)
            except sqlite3.OperationalError as e:
                logger.warning("Could not add column %s: %s", col_name, e)

    # Add deadline column to scholarships table if not exists
    cursor.execute("PRAGMA table_info(scholarships)")
    scholarship_cols = {row[1] for row in cursor.fetchall()}

    scholarship_new_cols = [
        ("deadline_date", "DATE"),
    ]

    for col_name, col_type in scholarship_new_cols:
        if col_name not in scholarship_cols:
            try:
                cursor.execute(f"ALTER TABLE scholarships ADD COLUMN {col_name} {col_type}")
                logger.info("Added column %s to scholarships table", col_name)
            except sqlite3.OperationalError as e:
                logger.warning("Could not add column %s: %s", col_name, e)

    conn.commit()
    conn.close()
    logger.info("Database migration completed")


if __name__ == "__main__":
    create_database()
    migrate_database()
