"""
Location Ecosystem Lookup Functions

Provides functions to retrieve and work with location ecosystem data
for post-masters career path calculations.
"""

from dataclasses import dataclass
from typing import Optional

from config import get_db, get_logger

logger = get_logger(__name__)


@dataclass
class LocationEcosystem:
    """Location ecosystem data for a city."""

    city: str
    country: str
    # Startup metrics
    startup_ecosystem_strength: float = 1.0
    vc_density: str = "low"
    startup_salary_discount: float = 0.7
    equity_multiple_median: float = 0.0
    # Big tech metrics
    bigtech_presence: str = "none"
    bigtech_salary_premium: float = 1.0
    # Remote work
    remote_arbitrage_factor: float = 1.0
    # Entrepreneur visas
    entrepreneur_visa_available: bool = False
    entrepreneur_visa_type: Optional[str] = None
    # Talent
    tech_talent_density: str = "low"
    notes: Optional[str] = None


# Default ecosystem for cities not in the database
DEFAULT_ECOSYSTEM = LocationEcosystem(
    city="Unknown",
    country="Unknown",
    startup_ecosystem_strength=0.8,
    vc_density="low",
    startup_salary_discount=0.7,
    equity_multiple_median=20,
    bigtech_presence="none",
    bigtech_salary_premium=0.9,
    remote_arbitrage_factor=1.0,
    entrepreneur_visa_available=False,
    entrepreneur_visa_type=None,
    tech_talent_density="low",
)

# Bigtech presence to startup probability modifier
BIGTECH_STARTUP_MODIFIER = {
    "hq": 1.15,  # HQ cities have stronger startup ecosystems
    "major_office": 1.05,
    "minor": 0.95,
    "none": 0.85,
}

# VC density to funding probability modifier
VC_FUNDING_MODIFIER = {
    "very_high": 1.3,
    "high": 1.15,
    "medium": 1.0,
    "low": 0.75,
}


def get_ecosystem(city: str, country: Optional[str] = None) -> LocationEcosystem:
    """
    Look up ecosystem data for a city.

    Args:
        city: City name (case-insensitive)
        country: Optional country to disambiguate (e.g., "Sydney" in Australia vs Canada)

    Returns:
        LocationEcosystem dataclass with all ecosystem metrics
    """
    with get_db() as conn:
        cursor = conn.cursor()

        if country:
            cursor.execute(
                """
                SELECT * FROM location_ecosystems
                WHERE LOWER(city) = LOWER(?) AND LOWER(country) = LOWER(?)
                """,
                (city, country),
            )
        else:
            cursor.execute(
                """
                SELECT * FROM location_ecosystems
                WHERE LOWER(city) = LOWER(?)
                ORDER BY startup_ecosystem_strength DESC
                LIMIT 1
                """,
                (city,),
            )

        row = cursor.fetchone()

    if not row:
        logger.debug("No ecosystem data for %s, %s - using defaults", city, country)
        return LocationEcosystem(city=city, country=country or "Unknown")

    return LocationEcosystem(
        city=row["city"],
        country=row["country"],
        startup_ecosystem_strength=row["startup_ecosystem_strength"] or 1.0,
        vc_density=row["vc_density"] or "low",
        startup_salary_discount=row["startup_salary_discount"] or 0.7,
        equity_multiple_median=row["equity_multiple_median"] or 0.0,
        bigtech_presence=row["bigtech_presence"] or "none",
        bigtech_salary_premium=row["bigtech_salary_premium"] or 1.0,
        remote_arbitrage_factor=row["remote_arbitrage_factor"] or 1.0,
        entrepreneur_visa_available=bool(row["entrepreneur_visa_available"]),
        entrepreneur_visa_type=row["entrepreneur_visa_type"],
        tech_talent_density=row["tech_talent_density"] or "low",
        notes=row["notes"],
    )


def get_ecosystem_by_country(country: str) -> Optional[LocationEcosystem]:
    """
    Get the primary ecosystem for a country (the city with highest startup strength).

    Useful when we only know the country (e.g., from a program's work country).

    Args:
        country: Country name

    Returns:
        LocationEcosystem for the strongest city in that country, or None
    """
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT * FROM location_ecosystems
            WHERE LOWER(country) = LOWER(?)
            ORDER BY startup_ecosystem_strength DESC
            LIMIT 1
            """,
            (country,),
        )
        row = cursor.fetchone()

    if not row:
        return None

    return LocationEcosystem(
        city=row["city"],
        country=row["country"],
        startup_ecosystem_strength=row["startup_ecosystem_strength"] or 1.0,
        vc_density=row["vc_density"] or "low",
        startup_salary_discount=row["startup_salary_discount"] or 0.7,
        equity_multiple_median=row["equity_multiple_median"] or 0.0,
        bigtech_presence=row["bigtech_presence"] or "none",
        bigtech_salary_premium=row["bigtech_salary_premium"] or 1.0,
        remote_arbitrage_factor=row["remote_arbitrage_factor"] or 1.0,
        entrepreneur_visa_available=bool(row["entrepreneur_visa_available"]),
        entrepreneur_visa_type=row["entrepreneur_visa_type"],
        tech_talent_density=row["tech_talent_density"] or "low",
        notes=row["notes"],
    )


def list_ecosystems(
    country: Optional[str] = None,
    min_startup_strength: Optional[float] = None,
    has_entrepreneur_visa: Optional[bool] = None,
) -> list[LocationEcosystem]:
    """
    List all ecosystems with optional filters.

    Args:
        country: Filter by country
        min_startup_strength: Filter by minimum startup ecosystem strength
        has_entrepreneur_visa: Filter to cities with entrepreneur visa paths

    Returns:
        List of LocationEcosystem objects
    """
    with get_db() as conn:
        cursor = conn.cursor()

        query = "SELECT * FROM location_ecosystems WHERE 1=1"
        params = []

        if country:
            query += " AND LOWER(country) = LOWER(?)"
            params.append(country)

        if min_startup_strength is not None:
            query += " AND startup_ecosystem_strength >= ?"
            params.append(min_startup_strength)

        if has_entrepreneur_visa is not None:
            query += " AND entrepreneur_visa_available = ?"
            params.append(1 if has_entrepreneur_visa else 0)

        query += " ORDER BY startup_ecosystem_strength DESC"
        cursor.execute(query, params)
        rows = cursor.fetchall()

    return [
        LocationEcosystem(
            city=row["city"],
            country=row["country"],
            startup_ecosystem_strength=row["startup_ecosystem_strength"] or 1.0,
            vc_density=row["vc_density"] or "low",
            startup_salary_discount=row["startup_salary_discount"] or 0.7,
            equity_multiple_median=row["equity_multiple_median"] or 0.0,
            bigtech_presence=row["bigtech_presence"] or "none",
            bigtech_salary_premium=row["bigtech_salary_premium"] or 1.0,
            remote_arbitrage_factor=row["remote_arbitrage_factor"] or 1.0,
            entrepreneur_visa_available=bool(row["entrepreneur_visa_available"]),
            entrepreneur_visa_type=row["entrepreneur_visa_type"],
            tech_talent_density=row["tech_talent_density"] or "low",
            notes=row["notes"],
        )
        for row in rows
    ]


def calculate_startup_success_modifier(ecosystem: LocationEcosystem) -> float:
    """
    Calculate the startup success probability modifier for a location.

    Combines startup ecosystem strength with VC density and bigtech presence.

    Returns:
        Multiplier to apply to base startup success probability (e.g., 1.5 = 50% boost)
    """
    base = ecosystem.startup_ecosystem_strength

    # Apply VC density modifier
    vc_mod = VC_FUNDING_MODIFIER.get(ecosystem.vc_density, 1.0)

    # Apply bigtech presence modifier (spillover effect)
    bigtech_mod = BIGTECH_STARTUP_MODIFIER.get(ecosystem.bigtech_presence, 1.0)

    # Combine multiplicatively but dampen extreme values
    raw = base * vc_mod * bigtech_mod
    # Clamp to reasonable range (0.3 to 2.5)
    return max(0.3, min(2.5, raw))


def calculate_bigtech_modifier(ecosystem: LocationEcosystem) -> float:
    """
    Calculate the big tech employment probability modifier for a location.

    Based on bigtech presence and salary premium.

    Returns:
        Multiplier for big tech path probability
    """
    presence_map = {
        "hq": 1.4,
        "major_office": 1.2,
        "minor": 0.8,
        "none": 0.5,
    }
    return presence_map.get(ecosystem.bigtech_presence, 1.0)


def calculate_remote_arbitrage_savings(
    remote_salary_usd: float,
    ecosystem: LocationEcosystem,
    us_tax_rate: float = 0.25,
) -> float:
    """
    Calculate annual savings from remote arbitrage (US salary, low-COL location).

    Args:
        remote_salary_usd: Annual remote salary in USD
        ecosystem: Location ecosystem for living
        us_tax_rate: Effective US tax rate (default 25%)

    Returns:
        Annual savings in USD considering arbitrage factor
    """
    # Remote arbitrage factor > 1 means living costs are lower than US baseline
    # A factor of 3.0 (Pakistan) means ~3x purchasing power
    # We estimate savings as: after_tax_salary * (1 - 1/arbitrage_factor)
    # This represents the "extra" savings from lower COL

    after_tax = remote_salary_usd * (1 - us_tax_rate)
    # Baseline savings in US (assuming 30% savings rate in HCOL)
    us_savings_rate = 0.30
    us_savings = after_tax * us_savings_rate

    # With arbitrage, you can save more because living costs are proportionally lower
    # If arbitrage_factor = 3.0, living costs are ~1/3 of US, so savings rate increases
    if ecosystem.remote_arbitrage_factor > 1.0:
        # Estimate: In HCOL, 70% goes to living costs. With arbitrage, this shrinks.
        living_cost_ratio = 1.0 / ecosystem.remote_arbitrage_factor
        new_living_cost_pct = 0.70 * living_cost_ratio
        arbitrage_savings_rate = 1.0 - new_living_cost_pct
        arbitrage_savings = after_tax * min(0.85, arbitrage_savings_rate)  # Cap at 85%
        return arbitrage_savings

    return us_savings


def is_startup_hub(ecosystem: LocationEcosystem) -> bool:
    """Check if a location qualifies as a startup hub."""
    return (
        ecosystem.startup_ecosystem_strength >= 1.0
        and ecosystem.vc_density in ("very_high", "high", "medium")
    )


def is_bigtech_hub(ecosystem: LocationEcosystem) -> bool:
    """Check if a location qualifies as a big tech hub."""
    return ecosystem.bigtech_presence in ("hq", "major_office")


def has_founder_visa_path(ecosystem: LocationEcosystem) -> bool:
    """Check if a location has a viable entrepreneur/founder visa path."""
    return ecosystem.entrepreneur_visa_available
