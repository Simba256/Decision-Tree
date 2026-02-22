"""
Market Mapping Module
=====================
Parses the `primary_market` field from the programs database into structured
work location data: (work_country, work_city, us_state).

This determines:
  - Which country's tax brackets to apply (work_country)
  - Which city's living costs to use (work_city)
  - Which US state tax to apply, if work_country == "USA" (us_state)

Rules:
  - Multi-market entries with "/" use the relocation destination (usually USA/UK/major market)
  - City names are mapped to their country
  - US markets are parsed for state-level tax mapping
  - Fallback: university country if primary_market is missing/unparseable

Data source: market_mappings and us_region_states tables in career_tree.db.
Loaded once at module import time and cached.
"""

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class MarketInfo:
    """Structured work location data."""

    work_country: str  # Country name for tax brackets
    work_city: str  # City/region for living costs
    us_state: Optional[str]  # US state code (2-letter) for state tax, or None


# ─── Database Loading ────────────────────────────────────────────────────────

DB_PATH = Path(__file__).parent / "career_tree.db"


def _load_us_region_states() -> dict[str, tuple[str, str]]:
    """Load US region keyword -> (state_code, display_city) from DB."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT region_keyword, state_code, display_city FROM us_region_states"
    )
    result = {row[0]: (row[1], row[2]) for row in cursor.fetchall()}
    conn.close()
    return result


def _load_market_mappings() -> dict[str, MarketInfo]:
    """Load primary_market -> MarketInfo from DB."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT primary_market, work_country, work_city, us_state FROM market_mappings"
    )
    result = {
        row[0]: MarketInfo(
            work_country=row[1],
            work_city=row[2],
            us_state=row[3],
        )
        for row in cursor.fetchall()
    }
    conn.close()
    return result


# ─── Module-level caches (loaded once at import time) ────────────────────────

# US_REGION_TO_STATE: keyword -> state_code (for _parse_us_market compatibility)
_US_REGION_DATA = _load_us_region_states()
US_REGION_TO_STATE: dict[str, str] = {k: v[0] for k, v in _US_REGION_DATA.items()}

# MARKET_MAP: primary_market string -> MarketInfo
MARKET_MAP: dict[str, MarketInfo] = _load_market_mappings()


# ─── US City/Region Parsing ─────────────────────────────────────────────────


def _parse_us_market(market_detail: str) -> MarketInfo:
    """Parse a US-specific market string like 'Bay Area', 'NYC/NJ', etc."""
    detail_lower = market_detail.lower().strip()

    for keyword, (state, display_city) in _US_REGION_DATA.items():
        if keyword in detail_lower:
            return MarketInfo(
                work_country="USA", work_city=display_city, us_state=state
            )

    return MarketInfo(work_country="USA", work_city="Bay Area", us_state="CA")


# ─── Public API ──────────────────────────────────────────────────────────────


def get_market_info(primary_market: str, university_country: str = None) -> MarketInfo:
    """
    Get structured market info for a program.

    Args:
        primary_market: The primary_market field from the DB
        university_country: Fallback country (university's country)

    Returns:
        MarketInfo with work_country, work_city, us_state
    """
    if not primary_market:
        country = university_country or "USA"
        return MarketInfo(work_country=country, work_city=country, us_state=None)

    # Direct lookup
    if primary_market in MARKET_MAP:
        return MARKET_MAP[primary_market]

    # Try to parse dynamically as fallback
    market = primary_market.strip()

    # Check if it starts with "USA"
    if market.startswith("USA"):
        detail = market.replace("USA", "").strip(" ()")
        return (
            _parse_us_market(detail) if detail else MarketInfo("USA", "Bay Area", "CA")
        )

    # Fallback to university country
    country = university_country or "Unknown"
    # Look up the default city for this country rather than using country name as city
    from living_costs import COUNTRY_DEFAULT_CITY

    default_city = COUNTRY_DEFAULT_CITY.get(country, country)
    return MarketInfo(work_country=country, work_city=default_city, us_state=None)


def get_study_country_for_living_cost(university_country: str) -> str:
    """
    Map university country to a living cost key for study years.
    Most map directly; multi-country programs use a sensible default.
    """
    if university_country == "Multi-country":
        return "France"
    return university_country


# ─── Validation ──────────────────────────────────────────────────────────────


def validate_all_markets():
    """Check that every primary_market in the DB has a mapping."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT DISTINCT primary_market FROM programs WHERE primary_market IS NOT NULL"
    )
    all_markets = [row[0] for row in cursor.fetchall()]
    conn.close()

    unmapped = []
    for market in all_markets:
        if market not in MARKET_MAP:
            unmapped.append(market)

    return unmapped


if __name__ == "__main__":
    unmapped = validate_all_markets()
    if unmapped:
        print(f"WARNING: {len(unmapped)} unmapped markets:")
        for m in unmapped:
            print(f"  - {m}")
    else:
        print(f"All markets mapped ({len(MARKET_MAP)} entries)")

    from collections import Counter

    countries = Counter(m.work_country for m in MARKET_MAP.values())
    print(f"\nWork country distribution ({len(countries)} countries):")
    for country, count in countries.most_common():
        print(f"  {country}: {count}")
