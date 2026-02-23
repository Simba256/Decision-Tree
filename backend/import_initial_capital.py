#!/usr/bin/env python3
"""
Import Initial Capital Requirements for Master's Programs

This script populates the initial_capital_usd field based on country-specific
requirements including:
- Blocked account requirements (Germany, Netherlands, etc.)
- First semester/year tuition payment
- Visa fees and health insurance surcharges
- Flight costs from Pakistan
- Initial accommodation deposits
- Proof of funds requirements
"""

import sqlite3
from config import DB_PATH, get_logger

logger = get_logger(__name__)

# ─── COUNTRY-SPECIFIC INITIAL CAPITAL RULES ─────────────────────────────────
# All values in USD. These are MINIMUM realistic requirements for a Pakistani student.

COUNTRY_RULES = {
    # ─── FULLY FUNDED - MINIMAL UPFRONT ─────────────────────────────────────
    "Saudi Arabia": {
        # KAUST: Full funding, flights covered, housing provided
        "base": 2000,  # Personal expenses, visa, initial settling
        "tuition_factor": 0,  # Tuition covered
        "notes": "KAUST covers everything including flights and housing"
    },

    # ─── ASIA-PACIFIC ───────────────────────────────────────────────────────
    "Japan": {
        # MEXT covers everything; self-funded needs more
        "base": 3000,  # Flights (~$800) + visa (~$50) + initial month (~$1500) + buffer
        "tuition_factor": 0.5,  # First semester if not MEXT
        "guaranteed_funded_base": 1500,  # MEXT: just personal expenses
        "notes": "MEXT fully funded; self-funded needs first semester"
    },
    "South Korea": {
        # KAIST/KGSP covers everything
        "base": 2500,  # Flights (~$700) + visa (~$60) + initial settling
        "tuition_factor": 0.5,  # First semester if not funded
        "guaranteed_funded_base": 1500,  # KAIST/KGSP: minimal
        "notes": "KAIST/KGSP fully funded; private programs need first semester"
    },
    "China": {
        # CSC covers tuition + stipend; self-funded needs proof of funds
        "base": 3000,  # Flights (~$500) + visa (~$140) + initial expenses
        "tuition_factor": 0.5,  # First semester for non-CSC
        "guaranteed_funded_base": 2000,  # CSC: flights + settling (stipend kicks in)
        "notes": "CSC fully funded; self-funded needs ~$10K proof of funds"
    },
    "Singapore": {
        # High cost but often partial funding
        "base": 8000,  # Visa + initial rent deposit + first month expenses
        "tuition_factor": 0.5,  # First semester
        "notes": "High cost of living; typically need 50% tuition upfront"
    },
    "Hong Kong": {
        # MPhil funded; taught MSc self-funded
        "base": 6000,  # Visa + initial costs + rent deposit (HK is expensive)
        "tuition_factor": 0.5,  # First semester
        "guaranteed_funded_base": 3000,  # MPhil: stipend covers most
        "notes": "MPhil studentships cover costs; taught MSc needs full funds"
    },
    "Taiwan": {
        # Government scholarships available
        "base": 3000,  # Flights + visa + initial month
        "tuition_factor": 0.5,
        "guaranteed_funded_base": 2000,
        "notes": "MOE/MOFA scholarships cover most costs"
    },
    "India": {
        # Very affordable, no blocked account
        "base": 2000,  # Flights (~$200) + visa + initial expenses
        "tuition_factor": 0.5,  # First semester
        "notes": "Low cost; IITs affordable for Pakistani students"
    },

    # ─── EUROPE ─────────────────────────────────────────────────────────────
    "Germany": {
        # Blocked account: €11,208/year (2024 rate)
        # Plus visa fee, semester contribution, initial settling
        "base": 15000,  # €11,208 blocked (~$12,200) + flights + visa + settling
        "tuition_factor": 0,  # Public unis mostly free (semester fees ~€300)
        "notes": "Blocked account €11,208 required; most programs tuition-free"
    },
    "Netherlands": {
        # Proof of funds: ~€900/month for residence permit
        # Non-EU tuition typically €15-20K/year
        "base": 14000,  # Proof of funds (~€10K) + flights + visa + deposit
        "tuition_factor": 0.5,  # First semester
        "notes": "Need proof of €900/month living; high non-EU tuition"
    },
    "Switzerland": {
        # Blocked account: CHF 21,000/year (~$23,500)
        # Low tuition at ETH/EPFL (~$1,500/year)
        "base": 25000,  # CHF 21K blocked + flights + visa + settling
        "tuition_factor": 0.25,  # Low tuition, but blocked account is main cost
        "notes": "CHF 21,000 blocked account required; tuition low at ETH/EPFL"
    },
    "France": {
        # Non-EU fees: ~€3,770/year (public), private varies
        # Proof of funds: ~€615/month
        "base": 8000,  # Proof of funds (~€7K) + flights + visa + settling
        "tuition_factor": 0.5,
        "notes": "Non-EU fees ~€3,770/year at public; need €615/month proof"
    },
    "Italy": {
        # Affordable, DSU grants for low-income
        "base": 6000,  # Flights + visa + proof of funds (~€6K) + settling
        "tuition_factor": 0.5,  # But DSU often covers this
        "guaranteed_funded_base": 3000,  # PoliMi + DSU: heavily subsidized
        "notes": "DSU regional grants cover most costs for Pakistani income"
    },
    "Spain": {
        # Relatively affordable
        "base": 7000,  # Proof of funds + flights + visa
        "tuition_factor": 0.5,
        "notes": "Lower cost than other Western Europe"
    },
    "Sweden": {
        # High tuition for non-EU, but many fee waivers
        "base": 12000,  # Proof of funds (SEK 9,450/month) + tuition deposit
        "tuition_factor": 0.5,
        "guaranteed_funded_base": 4000,  # With tuition waiver
        "notes": "High non-EU fees; many fee waivers available"
    },
    "Denmark": {
        # High tuition, proof of funds required
        "base": 12000,  # Proof of funds + flights + visa
        "tuition_factor": 0.5,
        "notes": "High non-EU tuition; limited funding"
    },
    "Finland": {
        # No tuition for EU; non-EU €10-18K/year, but scholarships available
        "base": 10000,  # Proof of funds (~€6,720/year) + flights + visa
        "tuition_factor": 0.5,
        "guaranteed_funded_base": 4000,  # With tuition waiver
        "notes": "Non-EU tuition ~€15K; many fee waivers available"
    },
    "Norway": {
        # No tuition even for non-EU at public unis!
        "base": 10000,  # Proof of funds (NOK 137,907/year ~$12,600) + visa + flights
        "tuition_factor": 0,  # Public unis free
        "notes": "NO TUITION even for non-EU; but high living costs"
    },
    "Austria": {
        # Low tuition (~€1,500/year for non-EU)
        "base": 8000,  # Proof of funds (~€1,200/month) + visa + flights
        "tuition_factor": 0.5,
        "notes": "Low tuition; need ~€1,200/month proof"
    },
    "Belgium": {
        # Moderate tuition
        "base": 8000,  # Proof of funds + flights + visa
        "tuition_factor": 0.5,
        "notes": "Moderate tuition; EU hub"
    },
    "UK": {
        # High tuition, CAS requirements
        # Immigration Health Surcharge: £1,035/year
        # Living costs proof: £1,334/month (outside London) for 9 months
        "base": 18000,  # IHS (~$1,300) + living proof (~$15K) + visa (~$500) + flights
        "tuition_factor": 0.5,  # Often need to pay first semester upfront
        "notes": "CAS requires full tuition deposit + living proof; IHS £1,035/yr"
    },
    "Ireland": {
        # Similar to UK
        "base": 12000,  # Proof of funds + visa + flights
        "tuition_factor": 0.5,
        "notes": "High non-EU tuition; EU work rights post-study"
    },
    "Czech Republic": {
        # Affordable, English programs available
        "base": 5000,  # Proof of funds + visa + flights
        "tuition_factor": 0.5,
        "notes": "Affordable; many English programs"
    },
    "Poland": {
        # Very affordable
        "base": 4000,  # Lower proof of funds requirement
        "tuition_factor": 0.5,
        "notes": "Very affordable; growing tech scene"
    },
    "Estonia": {
        # Digital nation, affordable
        "base": 5000,  # Proof of funds + visa + flights
        "tuition_factor": 0.5,
        "notes": "Affordable; strong tech ecosystem"
    },
    "Portugal": {
        # Affordable, growing tech scene
        "base": 6000,  # Proof of funds + visa + flights
        "tuition_factor": 0.5,
        "notes": "Affordable; Web Summit country"
    },

    # ─── NORTH AMERICA ──────────────────────────────────────────────────────
    "USA": {
        # I-20 requires proof of FULL year funding (tuition + living ~$25-40K)
        # SEVIS fee: $350
        # Visa fee: $185
        # Flights: ~$1,200
        "base": 5000,  # SEVIS + visa + flights + initial settling
        "tuition_factor": 0.5,  # First semester typically required
        "proof_of_funds_factor": 0.5,  # Additional proof beyond tuition
        "notes": "I-20 requires proof of full year funds; high upfront"
    },
    "Canada": {
        # Study permit requires proof of funds: $10,000 CAD + first year tuition
        # Biometrics: $85 CAD
        # Study permit: $150 CAD
        "base": 8000,  # CAD proof ($10K) + visa fees + flights + settling
        "tuition_factor": 0.5,  # First semester/year
        "notes": "Study permit needs CAD 10K + tuition proof"
    },

    # ─── AUSTRALIA/NZ ───────────────────────────────────────────────────────
    "Australia": {
        # Student visa requires proof: 12 months living (~AUD 24,505) + tuition
        # OSHC health insurance: ~AUD 600/year
        "base": 20000,  # High proof of funds + OSHC + visa + flights
        "tuition_factor": 0.5,  # First semester
        "notes": "High living proof (AUD 24,505/yr) + OSHC required"
    },
    "New Zealand": {
        # Proof of funds: NZD 20,000/year living
        "base": 16000,  # Proof of funds + visa + flights
        "tuition_factor": 0.5,
        "notes": "NZD 20K/year living proof required"
    },

    # ─── MIDDLE EAST ────────────────────────────────────────────────────────
    "Israel": {
        # Moderate costs, scholarships available
        "base": 5000,  # Flights + visa + initial
        "tuition_factor": 0.5,
        "notes": "Moderate costs; many scholarships for tech"
    },
    "Lebanon": {
        "base": 4000,
        "tuition_factor": 0.5,
        "notes": "Lower costs but economic instability"
    },
    "Egypt": {
        "base": 3000,
        "tuition_factor": 0.5,
        "notes": "Very affordable"
    },
    "Turkey": {
        # Türkiye Bursları covers everything
        "base": 3000,  # Flights + visa + initial
        "tuition_factor": 0.5,
        "guaranteed_funded_base": 1500,  # TB: flights covered, stipend immediate
        "notes": "Türkiye Bursları fully funded; private unis need funds"
    },

    # ─── LATIN AMERICA ──────────────────────────────────────────────────────
    "Brazil": {
        "base": 3500,
        "tuition_factor": 0.5,
        "notes": "Affordable; public unis nearly free"
    },
    "Mexico": {
        "base": 3500,
        "tuition_factor": 0.5,
        "notes": "Affordable; close to US market"
    },
    "Chile": {
        "base": 4000,
        "tuition_factor": 0.5,
        "notes": "Moderate costs; stable economy"
    },
    "Colombia": {
        "base": 3500,
        "tuition_factor": 0.5,
        "notes": "Affordable; growing tech scene"
    },

    # ─── AFRICA ─────────────────────────────────────────────────────────────
    "South Africa": {
        "base": 3000,
        "tuition_factor": 0.5,
        "notes": "Affordable; English medium"
    },

    # ─── SPECIAL CASES ──────────────────────────────────────────────────────
    "Multi-country": {
        # Erasmus Mundus: moves between countries
        "base": 5000,  # Initial costs covered by scholarship
        "tuition_factor": 0,  # EM scholarships cover tuition
        "notes": "Erasmus Mundus fully funded"
    },
}

# Default rule for countries not explicitly listed
DEFAULT_RULE = {
    "base": 8000,
    "tuition_factor": 0.5,
    "notes": "Standard international student requirements"
}


def calculate_initial_capital(program: dict, country: str, university_name: str) -> int:
    """
    Calculate initial capital requirement for a program.

    Args:
        program: Program dict with tuition_usd, aid_type, etc.
        country: Country name
        university_name: University name (for special cases)

    Returns:
        Initial capital requirement in USD
    """
    rule = COUNTRY_RULES.get(country, DEFAULT_RULE)
    tuition = program.get("tuition_usd", 0) or 0
    aid_type = program.get("aid_type", "none")

    # Check if this is a guaranteed funded program
    is_guaranteed_funded = aid_type == "guaranteed_funding"

    # Special university cases
    if university_name in ("KAUST",):
        return 2000  # Minimal - everything covered
    if university_name in ("KAIST", "POSTECH"):
        return 2000  # Guaranteed funding
    notes = program.get("notes") or ""
    program_name = program.get("program_name") or ""
    if "MEXT" in notes or "MEXT" in program_name:
        return 1500  # MEXT covers everything

    # Use guaranteed funded base if applicable
    if is_guaranteed_funded and "guaranteed_funded_base" in rule:
        base = rule["guaranteed_funded_base"]
        tuition_factor = 0  # Tuition covered
    else:
        base = rule["base"]
        tuition_factor = rule.get("tuition_factor", 0.5)

    # Calculate tuition component (first semester or as per factor)
    tuition_component = int(tuition * tuition_factor * 1000)  # tuition is in $K

    # Additional proof of funds (mainly for USA)
    proof_factor = rule.get("proof_of_funds_factor", 0)
    proof_component = int(tuition * proof_factor * 1000)

    total = base + tuition_component + proof_component

    return total


def import_initial_capital():
    """Populate initial_capital_usd for all programs."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Get all programs with university info
    cursor.execute("""
        SELECT
            p.id,
            p.program_name,
            p.tuition_usd,
            p.aid_type,
            p.notes,
            u.name as university_name,
            u.country
        FROM programs p
        JOIN universities u ON p.university_id = u.id
    """)

    programs = cursor.fetchall()
    updated = 0

    for prog in programs:
        program_dict = {
            "tuition_usd": prog["tuition_usd"],
            "aid_type": prog["aid_type"],
            "notes": prog["notes"],
            "program_name": prog["program_name"]
        }

        initial_capital = calculate_initial_capital(
            program_dict,
            prog["country"],
            prog["university_name"]
        )

        cursor.execute(
            "UPDATE programs SET initial_capital_usd = ? WHERE id = ?",
            (initial_capital, prog["id"])
        )
        updated += 1

        logger.debug(
            f"  {prog['university_name']:25} | {prog['country']:15} | "
            f"Tuition: ${(prog['tuition_usd'] or 0):,}K | "
            f"Initial Capital: ${initial_capital:,}"
        )

    conn.commit()
    conn.close()

    logger.info(f"Updated initial capital for {updated} programs")
    return updated


def print_summary():
    """Print summary of initial capital by country."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            u.country,
            COUNT(p.id) as count,
            AVG(p.initial_capital_usd) as avg_capital,
            MIN(p.initial_capital_usd) as min_capital,
            MAX(p.initial_capital_usd) as max_capital
        FROM programs p
        JOIN universities u ON p.university_id = u.id
        GROUP BY u.country
        ORDER BY avg_capital DESC
    """)

    print("\n" + "="*80)
    print("INITIAL CAPITAL REQUIREMENTS BY COUNTRY")
    print("="*80)
    print(f"{'Country':20} | {'Programs':>8} | {'Avg':>10} | {'Min':>10} | {'Max':>10}")
    print("-"*80)

    for row in cursor.fetchall():
        print(
            f"{row['country']:20} | {row['count']:>8} | "
            f"${row['avg_capital']:>8,.0f} | "
            f"${row['min_capital']:>8,} | "
            f"${row['max_capital']:>8,}"
        )

    conn.close()


if __name__ == "__main__":
    print("Importing initial capital requirements...")
    count = import_initial_capital()
    print(f"\nUpdated {count} programs")
    print_summary()
