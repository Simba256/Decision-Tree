"""
Import location ecosystem data into the database.
Populates the location_ecosystems table with startup/career ecosystem
metrics for major tech hubs worldwide.

Usage: python3 import_location_ecosystems.py
"""

import sqlite3

from config import DB_PATH, get_logger

logger = get_logger(__name__)

# ═══════════════════════════════════════════════════════════════════════════════
# Location Ecosystem Data
#
# startup_ecosystem_strength: Multiplier for startup success probability
#   - 1.0 = baseline (average tech city)
#   - SF = 1.8 (strongest), Karlsruhe = 0.6 (weak)
#
# vc_density: VC funding availability
#   - very_high: SF, NYC - abundant Series A-C funding
#   - high: Seattle, Boston, London, Singapore
#   - medium: Berlin, Austin, Toronto
#   - low: Most other cities
#
# startup_salary_discount: Typical startup salary vs big tech (0.5-0.9)
#
# equity_multiple_median: Expected equity value at exit (in $K)
#   - Series A employee: $50K median
#   - Seed employee: $150K median (higher risk, higher reward)
#   - Founder: variable based on outcome
#
# bigtech_presence: Major tech company presence
#   - hq: HQ city (SF, Seattle, NYC for some)
#   - major_office: Significant engineering office
#   - minor: Small office or remote hub
#   - none: No significant presence
#
# bigtech_salary_premium: Salary multiplier vs market average
#
# remote_arbitrage_factor: Cost-of-living arbitrage potential
#   - Higher = better arbitrage (Lahore = 3.0, SF = 0.3)
#
# entrepreneur_visa_available: 1 if entrepreneur visa path exists
#
# entrepreneur_visa_type: Specific visa (O-1, Start-up Visa, Innovator, etc.)
#
# tech_talent_density: Availability of tech talent for hiring
#   - very_high: SF, Seattle, NYC
#   - high: Boston, Austin, London, Berlin
#   - medium: Most tech hubs
#   - low: Emerging markets
# ═══════════════════════════════════════════════════════════════════════════════

LOCATION_ECOSYSTEMS = [
    # ─── US Tech Hubs ─────────────────────────────────────────────────────────
    {
        "city": "San Francisco",
        "country": "USA",
        "startup_ecosystem_strength": 1.8,
        "vc_density": "very_high",
        "startup_salary_discount": 0.75,
        "equity_multiple_median": 75,
        "bigtech_presence": "hq",
        "bigtech_salary_premium": 1.4,
        "remote_arbitrage_factor": 0.3,
        "entrepreneur_visa_available": 1,
        "entrepreneur_visa_type": "O-1 Extraordinary Ability",
        "tech_talent_density": "very_high",
        "notes": "Global startup capital. FAANG HQs. Highest comp, highest COL.",
    },
    {
        "city": "New York",
        "country": "USA",
        "startup_ecosystem_strength": 1.5,
        "vc_density": "very_high",
        "startup_salary_discount": 0.75,
        "equity_multiple_median": 60,
        "bigtech_presence": "major_office",
        "bigtech_salary_premium": 1.35,
        "remote_arbitrage_factor": 0.35,
        "entrepreneur_visa_available": 1,
        "entrepreneur_visa_type": "O-1 Extraordinary Ability",
        "tech_talent_density": "very_high",
        "notes": "Strong fintech, adtech, media-tech. Growing AI scene.",
    },
    {
        "city": "Seattle",
        "country": "USA",
        "startup_ecosystem_strength": 1.4,
        "vc_density": "high",
        "startup_salary_discount": 0.75,
        "equity_multiple_median": 55,
        "bigtech_presence": "hq",
        "bigtech_salary_premium": 1.35,
        "remote_arbitrage_factor": 0.4,
        "entrepreneur_visa_available": 1,
        "entrepreneur_visa_type": "O-1 Extraordinary Ability",
        "tech_talent_density": "very_high",
        "notes": "Amazon, Microsoft HQs. Strong cloud/AI talent.",
    },
    {
        "city": "Austin",
        "country": "USA",
        "startup_ecosystem_strength": 1.25,
        "vc_density": "medium",
        "startup_salary_discount": 0.7,
        "equity_multiple_median": 45,
        "bigtech_presence": "major_office",
        "bigtech_salary_premium": 1.2,
        "remote_arbitrage_factor": 0.5,
        "entrepreneur_visa_available": 1,
        "entrepreneur_visa_type": "O-1 Extraordinary Ability",
        "tech_talent_density": "high",
        "notes": "Tesla, Oracle relocations. Growing startup scene. No state tax.",
    },
    {
        "city": "Boston",
        "country": "USA",
        "startup_ecosystem_strength": 1.3,
        "vc_density": "high",
        "startup_salary_discount": 0.7,
        "equity_multiple_median": 50,
        "bigtech_presence": "major_office",
        "bigtech_salary_premium": 1.25,
        "remote_arbitrage_factor": 0.45,
        "entrepreneur_visa_available": 1,
        "entrepreneur_visa_type": "O-1 Extraordinary Ability",
        "tech_talent_density": "high",
        "notes": "Strong biotech, AI/ML from MIT/Harvard pipeline.",
    },
    {
        "city": "Los Angeles",
        "country": "USA",
        "startup_ecosystem_strength": 1.15,
        "vc_density": "medium",
        "startup_salary_discount": 0.7,
        "equity_multiple_median": 40,
        "bigtech_presence": "major_office",
        "bigtech_salary_premium": 1.2,
        "remote_arbitrage_factor": 0.4,
        "entrepreneur_visa_available": 1,
        "entrepreneur_visa_type": "O-1 Extraordinary Ability",
        "tech_talent_density": "high",
        "notes": "Entertainment tech, SpaceX, gaming. Growing AI scene.",
    },
    # ─── UK / Europe ──────────────────────────────────────────────────────────
    {
        "city": "London",
        "country": "UK",
        "startup_ecosystem_strength": 1.3,
        "vc_density": "high",
        "startup_salary_discount": 0.65,
        "equity_multiple_median": 45,
        "bigtech_presence": "major_office",
        "bigtech_salary_premium": 1.2,
        "remote_arbitrage_factor": 0.5,
        "entrepreneur_visa_available": 1,
        "entrepreneur_visa_type": "Innovator Founder Visa",
        "tech_talent_density": "high",
        "notes": "Europe's largest tech hub. Strong fintech. DeepMind.",
    },
    {
        "city": "Berlin",
        "country": "Germany",
        "startup_ecosystem_strength": 1.1,
        "vc_density": "medium",
        "startup_salary_discount": 0.6,
        "equity_multiple_median": 35,
        "bigtech_presence": "minor",
        "bigtech_salary_premium": 1.0,
        "remote_arbitrage_factor": 0.7,
        "entrepreneur_visa_available": 1,
        "entrepreneur_visa_type": "Freelance/Startup Visa",
        "tech_talent_density": "high",
        "notes": "Startup capital of Germany. Lower salaries but lower COL.",
    },
    {
        "city": "Munich",
        "country": "Germany",
        "startup_ecosystem_strength": 0.9,
        "vc_density": "medium",
        "startup_salary_discount": 0.65,
        "equity_multiple_median": 30,
        "bigtech_presence": "major_office",
        "bigtech_salary_premium": 1.15,
        "remote_arbitrage_factor": 0.6,
        "entrepreneur_visa_available": 1,
        "entrepreneur_visa_type": "Freelance/Startup Visa",
        "tech_talent_density": "high",
        "notes": "Strong automotive/industry tech. Google, Apple offices.",
    },
    {
        "city": "Karlsruhe",
        "country": "Germany",
        "startup_ecosystem_strength": 0.6,
        "vc_density": "low",
        "startup_salary_discount": 0.6,
        "equity_multiple_median": 20,
        "bigtech_presence": "minor",
        "bigtech_salary_premium": 0.9,
        "remote_arbitrage_factor": 0.75,
        "entrepreneur_visa_available": 1,
        "entrepreneur_visa_type": "Freelance/Startup Visa",
        "tech_talent_density": "medium",
        "notes": "KIT university hub. Limited startup ecosystem.",
    },
    {
        "city": "Amsterdam",
        "country": "Netherlands",
        "startup_ecosystem_strength": 1.0,
        "vc_density": "medium",
        "startup_salary_discount": 0.65,
        "equity_multiple_median": 35,
        "bigtech_presence": "major_office",
        "bigtech_salary_premium": 1.1,
        "remote_arbitrage_factor": 0.6,
        "entrepreneur_visa_available": 1,
        "entrepreneur_visa_type": "Startup Visa",
        "tech_talent_density": "medium",
        "notes": "Growing tech hub. Booking.com. Strong expat community.",
    },
    {
        "city": "Zurich",
        "country": "Switzerland",
        "startup_ecosystem_strength": 0.85,
        "vc_density": "medium",
        "startup_salary_discount": 0.7,
        "equity_multiple_median": 40,
        "bigtech_presence": "major_office",
        "bigtech_salary_premium": 1.3,
        "remote_arbitrage_factor": 0.35,
        "entrepreneur_visa_available": 0,
        "entrepreneur_visa_type": None,
        "tech_talent_density": "medium",
        "notes": "Google Zurich. ETH pipeline. High salaries, high COL.",
    },
    {
        "city": "Paris",
        "country": "France",
        "startup_ecosystem_strength": 1.0,
        "vc_density": "medium",
        "startup_salary_discount": 0.6,
        "equity_multiple_median": 30,
        "bigtech_presence": "major_office",
        "bigtech_salary_premium": 1.05,
        "remote_arbitrage_factor": 0.55,
        "entrepreneur_visa_available": 1,
        "entrepreneur_visa_type": "French Tech Visa",
        "tech_talent_density": "high",
        "notes": "Station F. Growing AI scene. Strong government support.",
    },
    # ─── Canada ───────────────────────────────────────────────────────────────
    {
        "city": "Toronto",
        "country": "Canada",
        "startup_ecosystem_strength": 1.1,
        "vc_density": "medium",
        "startup_salary_discount": 0.65,
        "equity_multiple_median": 40,
        "bigtech_presence": "major_office",
        "bigtech_salary_premium": 1.1,
        "remote_arbitrage_factor": 0.6,
        "entrepreneur_visa_available": 1,
        "entrepreneur_visa_type": "Start-up Visa Program",
        "tech_talent_density": "high",
        "notes": "Canada's largest tech hub. Strong AI research (Vector).",
    },
    {
        "city": "Vancouver",
        "country": "Canada",
        "startup_ecosystem_strength": 0.95,
        "vc_density": "medium",
        "startup_salary_discount": 0.65,
        "equity_multiple_median": 35,
        "bigtech_presence": "major_office",
        "bigtech_salary_premium": 1.05,
        "remote_arbitrage_factor": 0.55,
        "entrepreneur_visa_available": 1,
        "entrepreneur_visa_type": "Start-up Visa Program",
        "tech_talent_density": "medium",
        "notes": "Amazon, Microsoft offices. Gaming industry hub.",
    },
    # ─── Asia-Pacific ─────────────────────────────────────────────────────────
    {
        "city": "Singapore",
        "country": "Singapore",
        "startup_ecosystem_strength": 1.2,
        "vc_density": "high",
        "startup_salary_discount": 0.7,
        "equity_multiple_median": 45,
        "bigtech_presence": "major_office",
        "bigtech_salary_premium": 1.15,
        "remote_arbitrage_factor": 0.5,
        "entrepreneur_visa_available": 1,
        "entrepreneur_visa_type": "EntrePass",
        "tech_talent_density": "medium",
        "notes": "SEA startup hub. Regional HQs. Low tax, high COL.",
    },
    {
        "city": "Tokyo",
        "country": "Japan",
        "startup_ecosystem_strength": 0.8,
        "vc_density": "medium",
        "startup_salary_discount": 0.6,
        "equity_multiple_median": 25,
        "bigtech_presence": "major_office",
        "bigtech_salary_premium": 1.0,
        "remote_arbitrage_factor": 0.6,
        "entrepreneur_visa_available": 1,
        "entrepreneur_visa_type": "Startup Visa",
        "tech_talent_density": "high",
        "notes": "Large market but conservative VC culture. Language barrier.",
    },
    {
        "city": "Hong Kong",
        "country": "Hong Kong",
        "startup_ecosystem_strength": 0.9,
        "vc_density": "medium",
        "startup_salary_discount": 0.7,
        "equity_multiple_median": 35,
        "bigtech_presence": "minor",
        "bigtech_salary_premium": 1.1,
        "remote_arbitrage_factor": 0.45,
        "entrepreneur_visa_available": 1,
        "entrepreneur_visa_type": "GEP Entrepreneur Visa",
        "tech_talent_density": "medium",
        "notes": "Finance/fintech hub. Gateway to China. High COL.",
    },
    {
        "city": "Sydney",
        "country": "Australia",
        "startup_ecosystem_strength": 0.95,
        "vc_density": "medium",
        "startup_salary_discount": 0.65,
        "equity_multiple_median": 35,
        "bigtech_presence": "major_office",
        "bigtech_salary_premium": 1.1,
        "remote_arbitrage_factor": 0.5,
        "entrepreneur_visa_available": 1,
        "entrepreneur_visa_type": "Business Innovation Visa",
        "tech_talent_density": "medium",
        "notes": "Australia's largest tech hub. Atlassian HQ. Growing scene.",
    },
    {
        "city": "Seoul",
        "country": "South Korea",
        "startup_ecosystem_strength": 0.85,
        "vc_density": "medium",
        "startup_salary_discount": 0.6,
        "equity_multiple_median": 30,
        "bigtech_presence": "minor",
        "bigtech_salary_premium": 0.95,
        "remote_arbitrage_factor": 0.65,
        "entrepreneur_visa_available": 1,
        "entrepreneur_visa_type": "Startup Visa (D-10-2)",
        "tech_talent_density": "high",
        "notes": "Samsung, LG. Strong local startups. Language barrier.",
    },
    # ─── Middle East ──────────────────────────────────────────────────────────
    {
        "city": "Dubai",
        "country": "UAE",
        "startup_ecosystem_strength": 0.75,
        "vc_density": "medium",
        "startup_salary_discount": 0.7,
        "equity_multiple_median": 30,
        "bigtech_presence": "minor",
        "bigtech_salary_premium": 1.0,
        "remote_arbitrage_factor": 0.6,
        "entrepreneur_visa_available": 1,
        "entrepreneur_visa_type": "Golden Visa / Freelance Visa",
        "tech_talent_density": "low",
        "notes": "Tax-free. Growing tech scene. Hub for MENA region.",
    },
    # ─── Pakistan (Return Path) ───────────────────────────────────────────────
    {
        "city": "Lahore",
        "country": "Pakistan",
        "startup_ecosystem_strength": 0.4,
        "vc_density": "low",
        "startup_salary_discount": 0.5,
        "equity_multiple_median": 15,
        "bigtech_presence": "none",
        "bigtech_salary_premium": 0.6,
        "remote_arbitrage_factor": 3.0,
        "entrepreneur_visa_available": 0,
        "entrepreneur_visa_type": None,
        "tech_talent_density": "medium",
        "notes": "Growing startup scene. Strong remote arbitrage potential.",
    },
    {
        "city": "Karachi",
        "country": "Pakistan",
        "startup_ecosystem_strength": 0.45,
        "vc_density": "low",
        "startup_salary_discount": 0.5,
        "equity_multiple_median": 15,
        "bigtech_presence": "none",
        "bigtech_salary_premium": 0.6,
        "remote_arbitrage_factor": 3.0,
        "entrepreneur_visa_available": 0,
        "entrepreneur_visa_type": None,
        "tech_talent_density": "medium",
        "notes": "Larger business hub. Systems Limited, Folio3.",
    },
    {
        "city": "Islamabad",
        "country": "Pakistan",
        "startup_ecosystem_strength": 0.35,
        "vc_density": "low",
        "startup_salary_discount": 0.5,
        "equity_multiple_median": 10,
        "bigtech_presence": "none",
        "bigtech_salary_premium": 0.6,
        "remote_arbitrage_factor": 3.2,
        "entrepreneur_visa_available": 0,
        "entrepreneur_visa_type": None,
        "tech_talent_density": "low",
        "notes": "Government/defense tech. NUST pipeline. Smaller scene.",
    },
    # ─── Additional European Cities ───────────────────────────────────────────
    {
        "city": "Dublin",
        "country": "Ireland",
        "startup_ecosystem_strength": 0.9,
        "vc_density": "medium",
        "startup_salary_discount": 0.65,
        "equity_multiple_median": 35,
        "bigtech_presence": "major_office",
        "bigtech_salary_premium": 1.15,
        "remote_arbitrage_factor": 0.55,
        "entrepreneur_visa_available": 1,
        "entrepreneur_visa_type": "Start-up Entrepreneur Programme",
        "tech_talent_density": "medium",
        "notes": "EU HQs for US tech giants. Strong tax benefits.",
    },
    {
        "city": "Stockholm",
        "country": "Sweden",
        "startup_ecosystem_strength": 1.15,
        "vc_density": "high",
        "startup_salary_discount": 0.65,
        "equity_multiple_median": 45,
        "bigtech_presence": "minor",
        "bigtech_salary_premium": 1.0,
        "remote_arbitrage_factor": 0.55,
        "entrepreneur_visa_available": 1,
        "entrepreneur_visa_type": "Self-Employment Permit",
        "tech_talent_density": "high",
        "notes": "Spotify, Klarna, King. Strong unicorn track record.",
    },
]


def import_location_ecosystems():
    """Import all location ecosystem data into the database."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    inserted = 0
    updated = 0

    for eco in LOCATION_ECOSYSTEMS:
        cursor.execute(
            """
            INSERT INTO location_ecosystems (
                city, country,
                startup_ecosystem_strength, vc_density,
                startup_salary_discount, equity_multiple_median,
                bigtech_presence, bigtech_salary_premium,
                remote_arbitrage_factor,
                entrepreneur_visa_available, entrepreneur_visa_type,
                tech_talent_density, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(city, country) DO UPDATE SET
                startup_ecosystem_strength = excluded.startup_ecosystem_strength,
                vc_density = excluded.vc_density,
                startup_salary_discount = excluded.startup_salary_discount,
                equity_multiple_median = excluded.equity_multiple_median,
                bigtech_presence = excluded.bigtech_presence,
                bigtech_salary_premium = excluded.bigtech_salary_premium,
                remote_arbitrage_factor = excluded.remote_arbitrage_factor,
                entrepreneur_visa_available = excluded.entrepreneur_visa_available,
                entrepreneur_visa_type = excluded.entrepreneur_visa_type,
                tech_talent_density = excluded.tech_talent_density,
                notes = excluded.notes
            """,
            (
                eco["city"],
                eco["country"],
                eco["startup_ecosystem_strength"],
                eco["vc_density"],
                eco["startup_salary_discount"],
                eco["equity_multiple_median"],
                eco["bigtech_presence"],
                eco["bigtech_salary_premium"],
                eco["remote_arbitrage_factor"],
                eco["entrepreneur_visa_available"],
                eco.get("entrepreneur_visa_type"),
                eco["tech_talent_density"],
                eco.get("notes"),
            ),
        )
        if cursor.rowcount == 1:
            inserted += 1
        else:
            updated += 1

    conn.commit()
    conn.close()

    logger.info(
        "Location ecosystems imported: %d inserted, %d updated", inserted, updated
    )
    return {"inserted": inserted, "updated": updated}


if __name__ == "__main__":
    import_location_ecosystems()
    print(f"Imported {len(LOCATION_ECOSYSTEMS)} location ecosystems.")
