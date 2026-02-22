"""
Living Costs Module
===================
Annual living costs by city/market for three household profiles:
  - "student": student housing (~70% rent) + reduced expenses during study
  - "single": single person, private apartment, post-graduation
  - "family": couple + 1 child (bigger apartment, childcare, higher food/transport)

Two lifestyle tiers:
  - "frugal" (default): outer-area apartment, cook at home, basic social, no car
  - "comfortable": better neighbourhood, dining out 2-3x/week, gym, modest car
    in car-dependent cities, market-rate childcare, one annual vacation

All values in $K USD per year. Based on 2024 cost-of-living data.

Data source: living_costs and country_default_cities tables in career_tree.db.
Loaded once at module import time and cached.

Main entry point:
    get_annual_living_cost(work_city, household_type, country=None, lifestyle="frugal") -> cost_usd_k
"""

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "career_tree.db"

VALID_LIFESTYLES = ("frugal", "comfortable")
VALID_HOUSEHOLDS = ("student", "single", "family")


# ─── Database Loading ────────────────────────────────────────────────────────


def _load_city_costs() -> dict[str, dict[str, dict[str, float]]]:
    """Load per-city living costs from DB for both lifestyle tiers.

    Returns:
        {city: {"frugal": {"student": x, "single": y, "family": z},
                "comfortable": {"student": x, "single": y, "family": z}}}
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT city, student_cost_k, single_cost_k, family_cost_k, "
        "comfortable_student_cost_k, comfortable_single_cost_k, comfortable_family_cost_k "
        "FROM living_costs"
    )
    result = {}
    for row in cursor.fetchall():
        city = row[0]
        result[city] = {
            "frugal": {"student": row[1], "single": row[2], "family": row[3]},
            "comfortable": {
                "student": row[4] if row[4] is not None else row[1],
                "single": row[5] if row[5] is not None else row[2],
                "family": row[6] if row[6] is not None else row[3],
            },
        }
    conn.close()
    return result


def _load_country_default_cities() -> dict[str, str]:
    """Load country -> default city fallback mappings from DB."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT country, default_city FROM country_default_cities")
    result = {row[0]: row[1] for row in cursor.fetchall()}
    conn.close()
    return result


# ─── Module-level caches (loaded once at import time) ────────────────────────

CITY_COSTS: dict[str, dict[str, dict[str, float]]] = _load_city_costs()
COUNTRY_DEFAULT_CITY: dict[str, str] = _load_country_default_cities()

# Generic fallback costs for countries/cities not explicitly listed
GENERIC_COSTS = {
    "frugal": {"student": 12.0, "single": 22.0, "family": 45.0},
    "comfortable": {"student": 16.0, "single": 28.0, "family": 58.0},
}


# ─── University Country → Study Living Costs ────────────────────────────────
# During study years, costs are based on university location, not work market.
# Some university countries have no work market entry (e.g., Lebanon).

UNIVERSITY_COUNTRY_COSTS: dict[str, dict[str, dict[str, float]]] = {
    "Lebanon": {
        "frugal": {"student": 8.0, "single": 14.0, "family": 30.0},
        "comfortable": {"student": 11.0, "single": 19.0, "family": 40.0},
    },
    "Egypt": {
        "frugal": {"student": 4.0, "single": 8.0, "family": 18.0},
        "comfortable": {"student": 6.0, "single": 12.0, "family": 25.0},
    },
}


# ─── Public API ──────────────────────────────────────────────────────────────


def get_annual_living_cost(
    city: str, household_type: str, country: str = None, lifestyle: str = "frugal"
) -> float:
    """
    Get annual living cost for a city and household type.

    Args:
        city: City name (from MarketInfo.work_city)
        household_type: "student", "single", or "family"
        country: Optional country for fallback lookup
        lifestyle: "frugal" or "comfortable"

    Returns:
        Annual living cost in $K USD
    """
    assert household_type in VALID_HOUSEHOLDS, (
        f"Invalid household_type: {household_type}"
    )
    assert lifestyle in VALID_LIFESTYLES, f"Invalid lifestyle: {lifestyle}"

    # Direct city lookup
    if city in CITY_COSTS:
        return CITY_COSTS[city][lifestyle][household_type]

    # Try country fallback
    if country:
        default_city = COUNTRY_DEFAULT_CITY.get(country)
        if default_city and default_city in CITY_COSTS:
            return CITY_COSTS[default_city][lifestyle][household_type]

        # Check university-country-specific costs
        if country in UNIVERSITY_COUNTRY_COSTS:
            return UNIVERSITY_COUNTRY_COSTS[country][lifestyle][household_type]

    # Generic fallback
    return GENERIC_COSTS[lifestyle][household_type]


def get_study_living_cost(
    university_country: str, household_type: str, lifestyle: str = "frugal"
) -> float:
    """
    Get living cost during study years based on university country.

    Args:
        university_country: Country where the university is located
        household_type: "student" or "single"
        lifestyle: "frugal" or "comfortable"

    Returns:
        Annual living cost in $K USD
    """
    assert lifestyle in VALID_LIFESTYLES, f"Invalid lifestyle: {lifestyle}"

    # Check university-specific costs first
    if university_country in UNIVERSITY_COUNTRY_COSTS:
        return UNIVERSITY_COUNTRY_COSTS[university_country][lifestyle][household_type]

    # Use the country's default city
    default_city = COUNTRY_DEFAULT_CITY.get(university_country)
    if default_city and default_city in CITY_COSTS:
        return CITY_COSTS[default_city][lifestyle][household_type]

    return GENERIC_COSTS[lifestyle][household_type]


def get_pakistan_living_cost(household_type: str, lifestyle: str = "frugal") -> float:
    """Get Pakistan baseline living cost."""
    assert lifestyle in VALID_LIFESTYLES, f"Invalid lifestyle: {lifestyle}"
    return CITY_COSTS["Pakistan"][lifestyle][household_type]


# ─── Validation ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    for tier in VALID_LIFESTYLES:
        print(f"\n{'=' * 60}")
        print(f"  LIFESTYLE TIER: {tier.upper()}")
        print(f"{'=' * 60}")
        print(f"{'City':<20} {'Student':>8} {'Single':>8} {'Family':>8}")
        print("-" * 48)
        for city in sorted(CITY_COSTS.keys()):
            c = CITY_COSTS[city][tier]
            print(
                f"{city:<20} ${c['student']:>5.1f}K  ${c['single']:>5.1f}K  ${c['family']:>5.1f}K"
            )

    print(f"\nTotal cities: {len(CITY_COSTS)}")
    print(f"Country fallbacks: {len(COUNTRY_DEFAULT_CITY)}")
