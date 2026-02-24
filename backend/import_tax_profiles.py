"""
Import Tax Country Profiles
============================
Populates the tax_country_profiles table with configuration for each country.
This data drives the generic _calculate_country_tax() function.

Run: cd backend && python import_tax_profiles.py
"""

import sqlite3
from config import DB_PATH

# Country profiles: consolidated tax calculation parameters
# Each country specifies how to calculate total tax from gross income
TAX_PROFILES = [
    # USA handled separately (needs state)
    {
        "country": "USA",
        "currency": "USD",
        "calculation_strategy": "usa_state",
        "notes": "Handled by dedicated US tax logic with state-level taxes",
    },
    # UK - Personal Allowance taper
    {
        "country": "UK",
        "currency": "GBP",
        "personal_allowance_lc": 12570,
        "pa_taper_start_lc": 100000,
        "pa_taper_rate": 0.5,
        "calculation_strategy": "uk_pa_taper",
        "notes": "PA reduced by £1 for every £2 over £100K",
    },
    # Canada - Federal + Ontario with surtax
    {
        "country": "Canada",
        "currency": "CAD",
        "calculation_strategy": "canada_surtax",
        "notes": "Federal + Ontario provincial with surtax, OHP, CPP/EI",
    },
    # Germany - Income tax + Soli + Social
    {
        "country": "Germany",
        "currency": "EUR",
        "social_rate": 0.205,
        "social_cap_lc": 90600,
        "surtax_rate": 0.055,
        "surtax_threshold_lc": 18130,
        "calculation_strategy": "standard",
        "notes": "Solidaritätszuschlag 5.5% on income tax if tax > €18,130",
    },
    # Switzerland - Federal + Cantonal + Social
    # Values must match tax_config table: cantonal=0.12, social=0.134, cap=148200
    {
        "country": "Switzerland",
        "currency": "CHF",
        "social_rate": 0.134,
        "social_cap_lc": 148200,
        "local_tax_rate": 0.12,
        "calculation_strategy": "standard",
        "notes": "Federal brackets + ~12% cantonal effective rate",
    },
    # France - 10% professional deduction
    {
        "country": "France",
        "currency": "EUR",
        "social_rate": 0.22,
        "professional_deduction_rate": 0.10,
        "calculation_strategy": "standard",
        "notes": "10% professional expense deduction before tax calculation",
    },
    # Netherlands - Integrated social in brackets
    {
        "country": "Netherlands",
        "currency": "EUR",
        "calculation_strategy": "standard",
        "notes": "Box 1 rates include social contributions",
    },
    # India - Cess on income tax
    {
        "country": "India",
        "currency": "INR",
        "social_rate": 0.12,  # EPF
        "cess_rate": 0.04,
        "calculation_strategy": "standard",
        "notes": "4% health & education cess on income tax + 12% EPF",
    },
    # Australia - Medicare levy
    {
        "country": "Australia",
        "currency": "AUD",
        "social_rate": 0.02,  # Medicare levy
        "calculation_strategy": "standard",
        "notes": "2% Medicare levy on gross income",
    },
    # Singapore - CPF
    {
        "country": "Singapore",
        "currency": "SGD",
        "social_rate": 0.20,
        "social_cap_lc": 72000,  # $6K/mo * 12
        "calculation_strategy": "standard",
        "notes": "20% CPF employee contribution, capped at $6K/mo",
    },
    # Hong Kong - Standard rate cap
    {
        "country": "Hong Kong",
        "currency": "HKD",
        "personal_allowance_lc": 132000,
        "standard_rate_cap": 0.15,
        "social_rate": 0.05,  # MPF
        "social_cap_lc": 216000,  # $1500/mo * 12 * 12 months
        "calculation_strategy": "hk_standard_cap",
        "notes": "Progressive or 15% standard rate, whichever is lower",
    },
    # Japan - Employment income deduction
    {
        "country": "Japan",
        "currency": "JPY",
        "social_rate": 0.1445,
        "social_cap_lc": 16800000,  # ~$1.4M/mo * 12
        "local_tax_rate": 0.10,  # Resident tax
        "surtax_rate": 0.021,  # Reconstruction surtax
        "calculation_strategy": "japan_deduction",
        "notes": "Employment deduction + basic exemption + reconstruction surtax",
    },
    # South Korea - Local tax on income tax
    {
        "country": "South Korea",
        "currency": "KRW",
        "social_rate": 0.094,
        "social_cap_lc": 65880000,  # ~$5.49M/mo * 12
        "local_tax_rate": 0.10,  # 10% of income tax
        "calculation_strategy": "local_tax_on_income",
        "notes": "10% local income tax on top of national income tax",
    },
    # Israel - Social flat rate
    {
        "country": "Israel",
        "currency": "ILS",
        "social_rate": 0.17,
        "calculation_strategy": "standard",
        "notes": "NI + Health = ~17%",
    },
    # China - Standard deduction + social
    {
        "country": "China",
        "currency": "CNY",
        "social_rate": 0.105,
        "social_cap_lc": 350000,
        "personal_allowance_lc": 60000,  # ¥5K/mo * 12
        "calculation_strategy": "deduction_after_social",
        "notes": "Social deducted before taxable income calculation",
    },
    # Sweden - Municipal + state + pension
    {
        "country": "Sweden",
        "currency": "SEK",
        "local_tax_rate": 0.32,  # Municipal
        "surtax_rate": 0.20,  # State rate
        "surtax_threshold_lc": 613900,
        "social_rate": 0.07,
        "social_cap_lc": 572000,
        "calculation_strategy": "sweden_municipal",
        "notes": "Municipal 32% + state 20% above threshold",
    },
    # Denmark - Complex with ceiling
    {
        "country": "Denmark",
        "currency": "DKK",
        "calculation_strategy": "denmark_complex",
        "notes": "AM-bidrag, municipal, state bottom/top, tax ceiling",
    },
    # Norway - Trinnskatt + flat
    {
        "country": "Norway",
        "currency": "NOK",
        "calculation_strategy": "norway_trinnskatt",
        "local_tax_rate": 0.22,
        "social_rate": 0.079,
        "personal_allowance_lc": 109950,
        "notes": "Trinnskatt brackets + 22% flat on ordinary income",
    },
    # Finland - State + municipal + social
    {
        "country": "Finland",
        "currency": "EUR",
        "local_tax_rate": 0.20,  # Municipal average
        "social_rate": 0.106,
        "calculation_strategy": "standard",
        "notes": "State brackets + ~20% municipal + ~10.6% social",
    },
    # Belgium - Personal allowance + municipal surcharge
    {
        "country": "Belgium",
        "currency": "EUR",
        "personal_allowance_lc": 10160,
        "social_rate": 0.1307,
        "surtax_rate": 0.07,  # Municipal surcharge on income tax
        "calculation_strategy": "surtax_on_income_tax",
        "notes": "Personal allowance + 7% municipal surcharge on income tax",
    },
    # Austria - Social with cap
    {
        "country": "Austria",
        "currency": "EUR",
        "social_rate": 0.1812,
        "social_cap_lc": 77616,
        "calculation_strategy": "standard",
        "notes": "~18.12% social contributions, capped",
    },
    # Italy - Regional + municipal surcharge
    {
        "country": "Italy",
        "currency": "EUR",
        "social_rate": 0.0919,
        "local_tax_rate": 0.025,  # Regional + municipal
        "calculation_strategy": "standard",
        "notes": "~2.5% regional+municipal surcharge + 9.19% social",
    },
    # Spain - Personal allowance + social cap
    {
        "country": "Spain",
        "currency": "EUR",
        "personal_allowance_lc": 5550,
        "social_rate": 0.0635,
        "social_cap_lc": 56844,
        "calculation_strategy": "standard",
        "notes": "Personal allowance + capped social contributions",
    },
    # Portugal - Social flat rate
    {
        "country": "Portugal",
        "currency": "EUR",
        "social_rate": 0.11,
        "calculation_strategy": "standard",
        "notes": "11% social contributions",
    },
    # Poland - Personal allowance + health
    {
        "country": "Poland",
        "currency": "PLN",
        "personal_allowance_lc": 30000,
        "social_rate": 0.1371,
        "social_cap_lc": 234720,
        "calculation_strategy": "poland_health",
        "notes": "Social + 9% health on (gross - social)",
    },
    # Czech Republic - Flat + social
    {
        "country": "Czech Republic",
        "currency": "CZK",
        "social_rate": 0.11,
        "calculation_strategy": "czech_flat",
        "notes": "15%/23% two-tier + 11% social",
    },
    # Estonia - Flat + basic exemption
    {
        "country": "Estonia",
        "currency": "EUR",
        "social_rate": 0.036,  # Unemployment 1.6% + pension 2%
        "calculation_strategy": "estonia_flat",
        "notes": "20% flat above basic exemption",
    },
    # New Zealand - ACC levy
    {
        "country": "New Zealand",
        "currency": "NZD",
        "social_rate": 0.016,  # ACC levy
        "calculation_strategy": "standard",
        "notes": "1.6% ACC levy",
    },
    # Taiwan - Standard deduction + social
    {
        "country": "Taiwan",
        "currency": "TWD",
        "personal_allowance_lc": 124000,
        "social_rate": 0.035,
        "calculation_strategy": "standard",
        "notes": "Standard deduction + ~3.5% NHI/Labor",
    },
    # Saudi Arabia - GOSI only
    {
        "country": "Saudi Arabia",
        "currency": "SAR",
        "social_rate": 0.0975,
        "calculation_strategy": "social_only",
        "notes": "0% income tax, GOSI ~9.75%",
    },
    # UAE - Zero tax
    {
        "country": "UAE",
        "currency": "AED",
        "calculation_strategy": "zero_tax",
        "notes": "0% income tax, no social contributions for expats",
    },
    # South Africa - Primary rebate + UIF
    {
        "country": "South Africa",
        "currency": "ZAR",
        "social_rate": 0.01,  # UIF
        "social_cap_lc": 212544,  # R17,712/mo * 12
        "calculation_strategy": "sa_rebate",
        "notes": "Primary rebate + 1% UIF (capped)",
    },
    # Egypt - Social flat
    {
        "country": "Egypt",
        "currency": "EGP",
        "social_rate": 0.11,
        "calculation_strategy": "standard",
        "notes": "~11% social contributions",
    },
    # Brazil - INSS capped
    {
        "country": "Brazil",
        "currency": "BRL",
        "social_rate": 0.11,
        "social_cap_lc": 105684,  # R$8,807.07/mo * 12
        "calculation_strategy": "standard",
        "notes": "INSS ~11% capped",
    },
    # Mexico - IMSS
    {
        "country": "Mexico",
        "currency": "MXN",
        "social_rate": 0.03,
        "calculation_strategy": "standard",
        "notes": "IMSS ~3% employee",
    },
    # Chile - AFP pension
    {
        "country": "Chile",
        "currency": "CLP",
        "social_rate": 0.125,
        "calculation_strategy": "standard",
        "notes": "AFP pension ~12.5%",
    },
    # Colombia - Pension + health
    {
        "country": "Colombia",
        "currency": "COP",
        "social_rate": 0.08,
        "calculation_strategy": "standard",
        "notes": "Pension 4% + Health 4%",
    },
    # Pakistan - Progressive brackets
    {
        "country": "Pakistan",
        "currency": "PKR",
        "calculation_strategy": "standard",
        "notes": "Progressive brackets, minimal social contributions",
    },
]


def import_profiles():
    """Import all tax country profiles into the database."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # First ensure the table exists
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tax_country_profiles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            country TEXT NOT NULL UNIQUE,
            currency TEXT NOT NULL DEFAULT 'USD',
            social_rate REAL DEFAULT 0,
            social_cap_lc REAL,
            surtax_rate REAL DEFAULT 0,
            surtax_threshold_lc REAL,
            personal_allowance_lc REAL DEFAULT 0,
            pa_taper_start_lc REAL,
            pa_taper_rate REAL DEFAULT 0.5,
            professional_deduction_rate REAL DEFAULT 0,
            local_tax_rate REAL DEFAULT 0,
            tax_ceiling REAL,
            cess_rate REAL DEFAULT 0,
            standard_rate_cap REAL,
            calculation_strategy TEXT DEFAULT 'standard',
            notes TEXT
        )
    """)

    for profile in TAX_PROFILES:
        cursor.execute(
            """
            INSERT OR REPLACE INTO tax_country_profiles (
                country, currency, social_rate, social_cap_lc,
                surtax_rate, surtax_threshold_lc,
                personal_allowance_lc, pa_taper_start_lc, pa_taper_rate,
                professional_deduction_rate, local_tax_rate, tax_ceiling,
                cess_rate, standard_rate_cap, calculation_strategy, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                profile.get("country"),
                profile.get("currency", "USD"),
                profile.get("social_rate", 0),
                profile.get("social_cap_lc"),
                profile.get("surtax_rate", 0),
                profile.get("surtax_threshold_lc"),
                profile.get("personal_allowance_lc", 0),
                profile.get("pa_taper_start_lc"),
                profile.get("pa_taper_rate", 0.5),
                profile.get("professional_deduction_rate", 0),
                profile.get("local_tax_rate", 0),
                profile.get("tax_ceiling"),
                profile.get("cess_rate", 0),
                profile.get("standard_rate_cap"),
                profile.get("calculation_strategy", "standard"),
                profile.get("notes"),
            ),
        )

    conn.commit()
    print(f"Imported {len(TAX_PROFILES)} tax country profiles")
    conn.close()


if __name__ == "__main__":
    import_profiles()
