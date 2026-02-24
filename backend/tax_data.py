"""
Tax Data Module
===============
Progressive tax brackets and social contributions for ~36 countries.
All data is 2024 rates. Salaries are in USD; brackets are converted from
local currency where needed using approximate 2024 exchange rates.

Data source: exchange_rates, tax_brackets, and tax_config tables in career_tree.db.
Loaded once at module import time and cached.

Main entry point:
    calculate_annual_tax(gross_usd_k, country, us_state=None) -> after_tax_usd_k

The function returns the annual after-tax income in $K USD.

Architecture:
    - Tax configuration loaded from DB (brackets, config values)
    - Strategy functions handle country-specific calculation patterns
    - _calculate_country_tax() dispatches to appropriate strategy
    - USA handled specially due to federal + state + city complexity
"""

import sqlite3
from dataclasses import dataclass
from typing import Optional, Callable

from config import DB_PATH


# ─── Database Loading ─────────────────────────────────────────────────────────


def _load_exchange_rates() -> dict[str, float]:
    """Load exchange rates (local currency per 1 USD) from DB."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT currency, rate_per_usd FROM exchange_rates")
    result = {row[0]: row[1] for row in cursor.fetchall()}
    conn.close()
    return result


def _load_all_brackets(
    fx: dict[str, float],
) -> dict[tuple[str, str], list[tuple[float, float]]]:
    """
    Load all tax brackets from DB, converting thresholds from local currency to USD.

    Returns dict keyed by (country, scope) -> list of (threshold_usd, rate) tuples.
    DB stores 999999999999 for infinity; we convert back to float('inf').
    DB stores thresholds in local currency; we convert to USD using FX rates.
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT country, scope, threshold_lc, rate, currency "
        "FROM tax_brackets ORDER BY country, scope, bracket_order"
    )
    brackets: dict[tuple[str, str], list[tuple[float, float]]] = {}
    for country, scope, threshold_lc, rate, currency in cursor.fetchall():
        key = (country, scope)
        if key not in brackets:
            brackets[key] = []

        # Convert 999999999999 back to infinity
        if threshold_lc >= 999999999999:
            threshold_usd = float("inf")
        elif currency == "USD":
            threshold_usd = threshold_lc
        else:
            # Convert from local currency to USD
            threshold_usd = threshold_lc / fx[currency]

        brackets[key].append((threshold_usd, rate))
    conn.close()
    return brackets


def _load_all_config() -> dict[tuple[str, str, str], float]:
    """
    Load all tax config parameters from DB.

    Returns dict keyed by (country, scope, config_key) -> config_value.
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT country, scope, config_key, config_value FROM tax_config")
    result = {(row[0], row[1], row[2]): row[3] for row in cursor.fetchall()}
    conn.close()
    return result


def _cfg(config: dict, country: str, scope: str, key: str) -> float:
    """Helper to get a config value, raising KeyError if missing."""
    return config[(country, scope, key)]


def _cfg_usd(
    config: dict, fx: dict, country: str, scope: str, key: str, currency: str
) -> float:
    """Helper to get a config value and convert from local currency to USD."""
    return config[(country, scope, key)] / fx[currency]


def _cfg_get(config: dict, country: str, scope: str, key: str, default: float = 0.0) -> float:
    """Helper to get a config value with a default if missing."""
    return config.get((country, scope, key), default)


# ─── Module-level caches (loaded once at import time) ─────────────────────────

FX = _load_exchange_rates()
_ALL_BRACKETS = _load_all_brackets(FX)
_ALL_CONFIG = _load_all_config()


# ─── Helper Functions ─────────────────────────────────────────────────────────


def _get_brackets(country: str, scope: str) -> list[tuple[float, float]]:
    """Get brackets for a (country, scope) pair from the loaded cache."""
    return _ALL_BRACKETS.get((country, scope), [])


def _lc_to_usd(amount_lc: float, currency: str) -> float:
    """Convert local currency amount to USD."""
    return amount_lc / FX[currency]


def _apply_brackets(gross_usd: float, brackets: list[tuple[float, float]]) -> float:
    """
    Apply progressive tax brackets.
    brackets: list of (threshold_usd, rate) tuples.
              threshold is the UPPER bound of the bracket (use float('inf') for last).
              The first bracket starts at 0.
    Returns total tax in USD.
    """
    tax = 0.0
    prev_threshold = 0.0
    for threshold, rate in brackets:
        if gross_usd <= prev_threshold:
            break
        taxable = min(gross_usd, threshold) - prev_threshold
        if taxable > 0:
            tax += taxable * rate
        prev_threshold = threshold
    return tax


# ═══════════════════════════════════════════════════════════════════════════════
# US TAX CALCULATION — Special handling for federal + state + city
# ═══════════════════════════════════════════════════════════════════════════════

US_FEDERAL_BRACKETS = _get_brackets("USA", "federal")

# Federal config
US_STANDARD_DEDUCTION = _cfg(_ALL_CONFIG, "USA", "federal", "standard_deduction")
SS_WAGE_BASE = _cfg(_ALL_CONFIG, "USA", "federal", "ss_wage_base")
SS_RATE = _cfg(_ALL_CONFIG, "USA", "federal", "ss_rate")
MEDICARE_RATE = _cfg(_ALL_CONFIG, "USA", "federal", "medicare_rate")
MEDICARE_SURTAX_THRESHOLD = _cfg(
    _ALL_CONFIG, "USA", "federal", "medicare_surtax_threshold"
)
MEDICARE_SURTAX_RATE = _cfg(_ALL_CONFIG, "USA", "federal", "medicare_surtax_rate")

# Build US_STATE_BRACKETS from DB
_US_STATE_CODES = ["CA", "NY", "MA", "IL", "PA", "NJ", "MD", "DC", "GA", "TX", "WA"]
US_STATE_BRACKETS: dict[str, list[tuple[float, float]]] = {}
for _sc in _US_STATE_CODES:
    _brackets = _get_brackets("USA", f"state_{_sc}")
    US_STATE_BRACKETS[_sc] = _brackets

# NYC city tax
NYC_CITY_BRACKETS = _get_brackets("USA", "city_NYC")

# State standard deductions from config
US_STATE_DEDUCTIONS: dict[str, float] = {}
for _sc in _US_STATE_CODES:
    _key = ("USA", f"state_{_sc}", "standard_deduction")
    US_STATE_DEDUCTIONS[_sc] = _ALL_CONFIG.get(_key, 0)


def _us_fica(gross_usd: float) -> float:
    """Calculate FICA taxes (Social Security + Medicare)."""
    ss = min(gross_usd, SS_WAGE_BASE) * SS_RATE
    medicare = gross_usd * MEDICARE_RATE
    if gross_usd > MEDICARE_SURTAX_THRESHOLD:
        medicare += (gross_usd - MEDICARE_SURTAX_THRESHOLD) * MEDICARE_SURTAX_RATE
    return ss + medicare


def _us_state_tax(gross_usd: float, state: str, city: str = None) -> float:
    """Calculate US state (and city) income tax."""
    brackets = US_STATE_BRACKETS.get(state, [])
    if not brackets:
        return 0.0

    deduction = US_STATE_DEDUCTIONS.get(state, 0)
    taxable = max(0, gross_usd - deduction)
    tax = _apply_brackets(taxable, brackets)

    # NYC city tax
    if state == "NY" and city in ("NYC", "New York"):
        tax += _apply_brackets(taxable, NYC_CITY_BRACKETS)

    return tax


def _us_total_tax(gross_usd: float, state: str = "CA", city: str = None) -> float:
    """Calculate total US tax: federal + state + FICA."""
    taxable_federal = max(0, gross_usd - US_STANDARD_DEDUCTION)
    federal = _apply_brackets(taxable_federal, US_FEDERAL_BRACKETS)
    state_tax = _us_state_tax(gross_usd, state, city)
    fica = _us_fica(gross_usd)
    return federal + state_tax + fica


# ═══════════════════════════════════════════════════════════════════════════════
# COUNTRY TAX STRATEGIES — Data-driven tax calculation
# Each strategy uses DB-loaded config values, not hardcoded constants
# ═══════════════════════════════════════════════════════════════════════════════


def _tax_uk(gross_usd: float) -> float:
    """UK income tax + National Insurance with PA taper."""
    # Personal allowance taper: reduced by £1 for every £2 over £100K
    pa = _cfg_usd(_ALL_CONFIG, FX, "UK", "income", "personal_allowance_lc", "GBP")
    taper_start = _cfg_usd(_ALL_CONFIG, FX, "UK", "income", "pa_taper_start_lc", "GBP")

    if gross_usd > taper_start:
        reduction = (gross_usd - taper_start) / 2
        pa = max(0, pa - reduction)

    # Income tax with adjusted PA
    brackets = [
        (pa, 0.0),
        (_lc_to_usd(50270, "GBP"), 0.20),
        (_lc_to_usd(125140, "GBP"), 0.40),
        (float("inf"), 0.45),
    ]
    income_tax = _apply_brackets(gross_usd, brackets)
    ni = _apply_brackets(gross_usd, _get_brackets("UK", "national_insurance"))
    return income_tax + ni


def _tax_canada(gross_usd: float) -> float:
    """Canada federal + Ontario provincial + surtax + OHP + CPP/EI."""
    # Federal
    federal_brackets = _get_brackets("Canada", "federal")
    federal_pa = _cfg_usd(_ALL_CONFIG, FX, "Canada", "federal", "personal_amount_lc", "CAD")
    federal_gross_tax = _apply_brackets(gross_usd, federal_brackets)
    federal_credit = federal_pa * federal_brackets[0][1] if federal_brackets else 0
    federal = max(0, federal_gross_tax - federal_credit)

    # Ontario provincial
    provincial_brackets = _get_brackets("Canada", "provincial_ontario")
    provincial_pa = _cfg_usd(
        _ALL_CONFIG, FX, "Canada", "provincial_ontario", "personal_amount_lc", "CAD"
    )
    provincial_gross_tax = _apply_brackets(gross_usd, provincial_brackets)
    provincial_credit = provincial_pa * provincial_brackets[0][1] if provincial_brackets else 0
    provincial_basic = max(0, provincial_gross_tax - provincial_credit)

    # Ontario surtax
    surtax_t1 = _lc_to_usd(
        _cfg(_ALL_CONFIG, "Canada", "provincial_ontario", "surtax_threshold1_lc"), "CAD"
    )
    surtax_r1 = _cfg(_ALL_CONFIG, "Canada", "provincial_ontario", "surtax_rate1")
    surtax_t2 = _lc_to_usd(
        _cfg(_ALL_CONFIG, "Canada", "provincial_ontario", "surtax_threshold2_lc"), "CAD"
    )
    surtax_r2 = _cfg(_ALL_CONFIG, "Canada", "provincial_ontario", "surtax_rate2")

    surtax = 0.0
    if provincial_basic > surtax_t1:
        surtax += surtax_r1 * (provincial_basic - surtax_t1)
    if provincial_basic > surtax_t2:
        surtax += surtax_r2 * (provincial_basic - surtax_t2)

    # Ontario Health Premium
    gross_cad = gross_usd * FX["CAD"]
    if gross_cad <= 20000:
        ohp = 0
    elif gross_cad <= 36000:
        ohp = min(300, 0.06 * (gross_cad - 20000))
    elif gross_cad <= 48000:
        ohp = 300 + min(150, 0.06 * (gross_cad - 36000))
    elif gross_cad <= 72000:
        ohp = 450 + min(150, 0.0625 * (gross_cad - 48000))
    elif gross_cad <= 200000:
        ohp = 600 + min(300, 0.25 * (gross_cad - 72000))
    else:
        ohp = 900
    ohp_usd = ohp / FX["CAD"]

    # CPP + EI
    cpp_rate = _cfg(_ALL_CONFIG, "Canada", "social", "cpp_rate")
    cpp_max = _cfg_usd(_ALL_CONFIG, FX, "Canada", "social", "cpp_max_lc", "CAD")
    ei_rate = _cfg(_ALL_CONFIG, "Canada", "social", "ei_rate")
    ei_max = _cfg_usd(_ALL_CONFIG, FX, "Canada", "social", "ei_max_lc", "CAD")

    cpp = min(gross_usd * cpp_rate, cpp_max)
    ei = min(gross_usd * ei_rate, ei_max)

    return federal + provincial_basic + surtax + ohp_usd + cpp + ei


def _tax_germany(gross_usd: float) -> float:
    """Germany income tax + Soli + social contributions."""
    brackets = _get_brackets("Germany", "income")
    income_tax = _apply_brackets(gross_usd, brackets)

    # Solidaritätszuschlag
    soli_threshold = _lc_to_usd(_cfg(_ALL_CONFIG, "Germany", "income", "soli_threshold_lc"), "EUR")
    soli_rate = _cfg(_ALL_CONFIG, "Germany", "income", "soli_rate")
    soli = income_tax * soli_rate if income_tax > soli_threshold else 0

    # Social
    social_rate = _cfg(_ALL_CONFIG, "Germany", "social", "rate")
    social_cap = _cfg_usd(_ALL_CONFIG, FX, "Germany", "social", "cap_lc", "EUR")
    social = min(gross_usd, social_cap) * social_rate

    return income_tax + soli + social


def _tax_switzerland(gross_usd: float) -> float:
    """Switzerland federal + cantonal + social contributions."""
    brackets = _get_brackets("Switzerland", "federal")
    federal = _apply_brackets(gross_usd, brackets)

    cantonal_rate = _cfg(_ALL_CONFIG, "Switzerland", "cantonal", "effective_rate")
    cantonal = gross_usd * cantonal_rate

    social_rate = _cfg(_ALL_CONFIG, "Switzerland", "social", "rate")
    social_cap = _cfg_usd(_ALL_CONFIG, FX, "Switzerland", "social", "cap_lc", "CHF")
    social = min(gross_usd, social_cap) * social_rate

    return federal + cantonal + social


def _tax_france(gross_usd: float) -> float:
    """France income tax + social contributions."""
    deduction_rate = _cfg(_ALL_CONFIG, "France", "income", "professional_deduction_rate")
    taxable = gross_usd * (1 - deduction_rate)

    brackets = _get_brackets("France", "income")
    income_tax = _apply_brackets(taxable, brackets)

    social_rate = _cfg(_ALL_CONFIG, "France", "social", "rate")
    social = gross_usd * social_rate

    return income_tax + social


def _tax_netherlands(gross_usd: float) -> float:
    """Netherlands income tax (Box 1 includes social)."""
    brackets = _get_brackets("Netherlands", "income")
    return _apply_brackets(gross_usd, brackets)


def _tax_india(gross_usd: float) -> float:
    """India income tax (new regime) + EPF."""
    brackets = _get_brackets("India", "income")
    income_tax = _apply_brackets(gross_usd, brackets)

    cess_rate = _cfg(_ALL_CONFIG, "India", "income", "cess_rate")
    cess = income_tax * cess_rate

    epf_rate = _cfg(_ALL_CONFIG, "India", "social", "epf_rate")
    epf = gross_usd * epf_rate

    return income_tax + cess + epf


def _tax_australia(gross_usd: float) -> float:
    """Australia income tax + Medicare levy."""
    brackets = _get_brackets("Australia", "income")
    income_tax = _apply_brackets(gross_usd, brackets)

    medicare_rate = _cfg(_ALL_CONFIG, "Australia", "social", "medicare_rate")
    medicare = gross_usd * medicare_rate

    return income_tax + medicare


def _tax_singapore(gross_usd: float) -> float:
    """Singapore income tax + CPF."""
    brackets = _get_brackets("Singapore", "income")
    income_tax = _apply_brackets(gross_usd, brackets)

    cpf_rate = _cfg(_ALL_CONFIG, "Singapore", "social", "cpf_rate")
    cpf_cap = _cfg_usd(_ALL_CONFIG, FX, "Singapore", "social", "cpf_cap_monthly_lc", "SGD") * 12
    cpf = min(gross_usd, cpf_cap) * cpf_rate

    return income_tax + cpf


def _tax_hong_kong(gross_usd: float) -> float:
    """Hong Kong salaries tax + MPF."""
    pa = _cfg_usd(_ALL_CONFIG, FX, "Hong Kong", "income", "personal_allowance_lc", "HKD")
    taxable = max(0, gross_usd - pa)

    brackets = _get_brackets("Hong Kong", "income")
    progressive = _apply_brackets(taxable, brackets)

    standard_rate = _cfg(_ALL_CONFIG, "Hong Kong", "income", "standard_rate")
    standard = gross_usd * standard_rate

    income_tax = min(progressive, standard)

    mpf_rate = _cfg(_ALL_CONFIG, "Hong Kong", "social", "mpf_rate")
    mpf_cap = _cfg_usd(_ALL_CONFIG, FX, "Hong Kong", "social", "mpf_cap_monthly_lc", "HKD") * 12
    mpf = min(gross_usd, mpf_cap) * mpf_rate

    return income_tax + mpf


def _tax_japan(gross_usd: float) -> float:
    """Japan income tax + resident tax + social insurance."""
    # Social insurance
    social_rate = _cfg(_ALL_CONFIG, "Japan", "social", "rate")
    social_cap = _cfg_usd(_ALL_CONFIG, FX, "Japan", "social", "cap_monthly_lc", "JPY") * 12
    social = min(gross_usd, social_cap) * social_rate

    # Employment income deduction (3-tier formula)
    emp_low_threshold = _lc_to_usd(
        _cfg(_ALL_CONFIG, "Japan", "income", "employment_deduction_low_threshold_lc"), "JPY"
    )
    emp_high_threshold = _lc_to_usd(
        _cfg(_ALL_CONFIG, "Japan", "income", "employment_deduction_high_threshold_lc"), "JPY"
    )

    if gross_usd < emp_low_threshold:
        emp_deduction = _lc_to_usd(
            _cfg(_ALL_CONFIG, "Japan", "income", "employment_deduction_low_lc"), "JPY"
        )
    elif gross_usd < emp_high_threshold:
        emp_deduction = gross_usd * _cfg(
            _ALL_CONFIG, "Japan", "income", "employment_deduction_mid_rate"
        ) + _lc_to_usd(
            _cfg(_ALL_CONFIG, "Japan", "income", "employment_deduction_mid_add_lc"), "JPY"
        )
    else:
        emp_deduction = _lc_to_usd(
            _cfg(_ALL_CONFIG, "Japan", "income", "employment_deduction_high_lc"), "JPY"
        )

    # Basic exemption
    basic_exemption = _lc_to_usd(_cfg(_ALL_CONFIG, "Japan", "income", "basic_exemption_lc"), "JPY")

    # Taxable income
    taxable = max(0, gross_usd - emp_deduction - social - basic_exemption)

    # National income tax + reconstruction surtax
    brackets = _get_brackets("Japan", "income")
    income_tax = _apply_brackets(taxable, brackets)
    reconstruction_rate = _cfg(_ALL_CONFIG, "Japan", "income", "reconstruction_surtax_rate")
    income_tax *= 1 + reconstruction_rate

    # Resident tax
    resident_rate = _cfg(_ALL_CONFIG, "Japan", "income", "resident_tax_rate")
    resident = taxable * resident_rate

    return income_tax + resident + social


def _tax_south_korea(gross_usd: float) -> float:
    """South Korea income + local + social."""
    brackets = _get_brackets("South Korea", "income")
    income_tax = _apply_brackets(gross_usd, brackets)

    local_rate = _cfg(_ALL_CONFIG, "South Korea", "income", "local_tax_rate")
    local_tax = income_tax * local_rate

    social_rate = _cfg(_ALL_CONFIG, "South Korea", "social", "rate")
    social_cap = _cfg_usd(_ALL_CONFIG, FX, "South Korea", "social", "cap_monthly_lc", "KRW") * 12
    social = min(gross_usd, social_cap) * social_rate

    return income_tax + local_tax + social


def _tax_israel(gross_usd: float) -> float:
    """Israel income tax + National Insurance + Health."""
    brackets = _get_brackets("Israel", "income")
    income_tax = _apply_brackets(gross_usd, brackets)

    social_rate = _cfg(_ALL_CONFIG, "Israel", "social", "rate")
    social = gross_usd * social_rate

    return income_tax + social


def _tax_china(gross_usd: float) -> float:
    """China IIT + social insurance."""
    social_rate = _cfg(_ALL_CONFIG, "China", "social", "rate")
    social_cap = _cfg_usd(_ALL_CONFIG, FX, "China", "social", "cap_lc", "CNY")
    social = min(gross_usd, social_cap) * social_rate

    deduction = _cfg_usd(_ALL_CONFIG, FX, "China", "income", "standard_deduction_lc", "CNY")
    taxable = max(0, gross_usd - deduction - social)

    brackets = _get_brackets("China", "income")
    income_tax = _apply_brackets(taxable, brackets)

    return income_tax + social


def _tax_sweden(gross_usd: float) -> float:
    """Sweden municipal + state + pension."""
    municipal_rate = _cfg(_ALL_CONFIG, "Sweden", "income", "municipal_rate")
    tax = gross_usd * municipal_rate

    state_threshold = _lc_to_usd(_cfg(_ALL_CONFIG, "Sweden", "income", "state_threshold_lc"), "SEK")
    state_rate = _cfg(_ALL_CONFIG, "Sweden", "income", "state_rate")
    if gross_usd > state_threshold:
        tax += (gross_usd - state_threshold) * state_rate

    pension_rate = _cfg(_ALL_CONFIG, "Sweden", "social", "pension_rate")
    pension_cap = _lc_to_usd(_cfg(_ALL_CONFIG, "Sweden", "social", "pension_cap_lc"), "SEK")
    social = min(gross_usd, pension_cap) * pension_rate

    return tax + social


def _tax_denmark(gross_usd: float) -> float:
    """Denmark AM-bidrag + municipal + state + ATP."""
    am_rate = _cfg(_ALL_CONFIG, "Denmark", "income", "am_bidrag_rate")
    am = gross_usd * am_rate
    taxable = gross_usd - am

    pa = _lc_to_usd(_cfg(_ALL_CONFIG, "Denmark", "income", "personal_allowance_lc"), "DKK")
    taxable = max(0, taxable - pa)

    municipal_rate = _cfg(_ALL_CONFIG, "Denmark", "income", "municipal_rate")
    municipal = taxable * municipal_rate

    state_bottom_rate = _cfg(_ALL_CONFIG, "Denmark", "income", "state_bottom_rate")
    state_bottom = taxable * state_bottom_rate

    top_threshold = _lc_to_usd(_cfg(_ALL_CONFIG, "Denmark", "income", "top_threshold_lc"), "DKK")
    top_rate = _cfg(_ALL_CONFIG, "Denmark", "income", "top_rate")
    state_top = max(0, taxable - top_threshold) * top_rate

    tax_ceiling = _cfg(_ALL_CONFIG, "Denmark", "income", "tax_ceiling")
    income_tax = min(municipal + state_bottom + state_top, taxable * tax_ceiling)

    atp = _lc_to_usd(_cfg(_ALL_CONFIG, "Denmark", "social", "atp_annual_lc"), "DKK")

    return am + income_tax + atp


def _tax_norway(gross_usd: float) -> float:
    """Norway trinnskatt + flat + social."""
    trinnskatt_brackets = _get_brackets("Norway", "trinnskatt")
    trinnskatt = _apply_brackets(gross_usd, trinnskatt_brackets)

    pa = _lc_to_usd(_cfg(_ALL_CONFIG, "Norway", "income", "personal_allowance_lc"), "NOK")
    taxable = max(0, gross_usd - pa)

    flat_rate = _cfg(_ALL_CONFIG, "Norway", "income", "flat_rate")
    flat_tax = taxable * flat_rate

    social_rate = _cfg(_ALL_CONFIG, "Norway", "social", "rate")
    social = gross_usd * social_rate

    return trinnskatt + flat_tax + social


def _tax_finland(gross_usd: float) -> float:
    """Finland state + municipal + social."""
    brackets = _get_brackets("Finland", "income")
    state_tax = _apply_brackets(gross_usd, brackets)

    municipal_rate = _cfg(_ALL_CONFIG, "Finland", "income", "municipal_rate")
    municipal = gross_usd * municipal_rate

    social_rate = _cfg(_ALL_CONFIG, "Finland", "social", "rate")
    social = gross_usd * social_rate

    return state_tax + municipal + social


def _tax_belgium(gross_usd: float) -> float:
    """Belgium income tax + municipal surcharge + social."""
    pa = _lc_to_usd(_cfg(_ALL_CONFIG, "Belgium", "income", "personal_allowance_lc"), "EUR")
    taxable = max(0, gross_usd - pa)

    brackets = _get_brackets("Belgium", "income")
    income_tax = _apply_brackets(taxable, brackets)

    surcharge_rate = _cfg(_ALL_CONFIG, "Belgium", "income", "municipal_surcharge_rate")
    municipal = income_tax * surcharge_rate

    social_rate = _cfg(_ALL_CONFIG, "Belgium", "social", "rate")
    social = gross_usd * social_rate

    return income_tax + municipal + social


def _tax_austria(gross_usd: float) -> float:
    """Austria income tax + social."""
    brackets = _get_brackets("Austria", "income")
    income_tax = _apply_brackets(gross_usd, brackets)

    social_rate = _cfg(_ALL_CONFIG, "Austria", "social", "rate")
    social_cap = _lc_to_usd(_cfg(_ALL_CONFIG, "Austria", "social", "cap_lc"), "EUR")
    social = min(gross_usd, social_cap) * social_rate

    return income_tax + social


def _tax_italy(gross_usd: float) -> float:
    """Italy income tax + surcharge + social."""
    brackets = _get_brackets("Italy", "income")
    income_tax = _apply_brackets(gross_usd, brackets)

    surcharge_rate = _cfg(_ALL_CONFIG, "Italy", "income", "surcharge_rate")
    surcharge = gross_usd * surcharge_rate

    social_rate = _cfg(_ALL_CONFIG, "Italy", "social", "rate")
    social = gross_usd * social_rate

    return income_tax + surcharge + social


def _tax_spain(gross_usd: float) -> float:
    """Spain income tax + social."""
    pa = _lc_to_usd(_cfg(_ALL_CONFIG, "Spain", "income", "personal_allowance_lc"), "EUR")
    taxable = max(0, gross_usd - pa)

    brackets = _get_brackets("Spain", "income")
    income_tax = _apply_brackets(taxable, brackets)

    social_rate = _cfg(_ALL_CONFIG, "Spain", "social", "rate")
    social_cap = _lc_to_usd(_cfg(_ALL_CONFIG, "Spain", "social", "cap_lc"), "EUR")
    social = min(gross_usd, social_cap) * social_rate

    return income_tax + social


def _tax_portugal(gross_usd: float) -> float:
    """Portugal income tax + social."""
    brackets = _get_brackets("Portugal", "income")
    income_tax = _apply_brackets(gross_usd, brackets)

    social_rate = _cfg(_ALL_CONFIG, "Portugal", "social", "rate")
    social = gross_usd * social_rate

    return income_tax + social


def _tax_poland(gross_usd: float) -> float:
    """Poland income tax + social + health."""
    pa = _lc_to_usd(_cfg(_ALL_CONFIG, "Poland", "income", "personal_allowance_lc"), "PLN")
    taxable = max(0, gross_usd - pa)

    brackets = _get_brackets("Poland", "income")
    income_tax = _apply_brackets(taxable, brackets)

    social_rate = _cfg(_ALL_CONFIG, "Poland", "social", "rate")
    social_cap = _lc_to_usd(_cfg(_ALL_CONFIG, "Poland", "social", "cap_lc"), "PLN")
    social = min(gross_usd, social_cap) * social_rate

    health_rate = _cfg(_ALL_CONFIG, "Poland", "social", "health_rate")
    health = (gross_usd - social) * health_rate

    return income_tax + social + health


def _tax_czech(gross_usd: float) -> float:
    """Czech Republic 15%/23% two-tier + social."""
    brackets = _get_brackets("Czech Republic", "income")
    if brackets:
        threshold = brackets[0][0]
        if gross_usd <= threshold:
            income_tax = gross_usd * 0.15
        else:
            income_tax = threshold * 0.15 + (gross_usd - threshold) * 0.23
    else:
        income_tax = gross_usd * 0.15

    social_rate = _cfg(_ALL_CONFIG, "Czech Republic", "social", "rate")
    social = gross_usd * social_rate

    return income_tax + social


def _tax_estonia(gross_usd: float) -> float:
    """Estonia 20% flat above basic exemption."""
    brackets = _get_brackets("Estonia", "income")
    if brackets:
        basic_exemption = brackets[0][0]
        taxable = max(0, gross_usd - basic_exemption)
        income_tax = taxable * 0.20
    else:
        income_tax = gross_usd * 0.20

    social_rate = _cfg(_ALL_CONFIG, "Estonia", "social", "rate")
    social = gross_usd * social_rate

    return income_tax + social


def _tax_new_zealand(gross_usd: float) -> float:
    """New Zealand income tax + ACC levy."""
    brackets = _get_brackets("New Zealand", "income")
    income_tax = _apply_brackets(gross_usd, brackets)

    acc_rate = _cfg(_ALL_CONFIG, "New Zealand", "social", "acc_rate")
    acc = gross_usd * acc_rate

    return income_tax + acc


def _tax_taiwan(gross_usd: float) -> float:
    """Taiwan income tax + social."""
    deduction = _lc_to_usd(_cfg(_ALL_CONFIG, "Taiwan", "income", "standard_deduction_lc"), "TWD")
    taxable = max(0, gross_usd - deduction)

    brackets = _get_brackets("Taiwan", "income")
    income_tax = _apply_brackets(taxable, brackets)

    social_rate = _cfg(_ALL_CONFIG, "Taiwan", "social", "rate")
    social = gross_usd * social_rate

    return income_tax + social


def _tax_saudi_arabia(gross_usd: float) -> float:
    """Saudi Arabia: 0% income tax, GOSI only."""
    gosi_rate = _cfg(_ALL_CONFIG, "Saudi Arabia", "social", "gosi_rate")
    return gross_usd * gosi_rate


def _tax_uae(gross_usd: float) -> float:
    """UAE: 0% income tax, no social for expats."""
    return 0.0


def _tax_south_africa(gross_usd: float) -> float:
    """South Africa income tax with rebate + UIF."""
    brackets = _get_brackets("South Africa", "income")
    rebate = _lc_to_usd(_cfg(_ALL_CONFIG, "South Africa", "income", "primary_rebate_lc"), "ZAR")
    income_tax = max(0, _apply_brackets(gross_usd, brackets) - rebate)

    uif_rate = _cfg(_ALL_CONFIG, "South Africa", "social", "uif_rate")
    uif_cap = _lc_to_usd(
        _cfg(_ALL_CONFIG, "South Africa", "social", "uif_cap_monthly_lc") * 12, "ZAR"
    )
    uif = min(gross_usd * uif_rate, uif_cap)

    return income_tax + uif


def _tax_egypt(gross_usd: float) -> float:
    """Egypt income tax + social."""
    brackets = _get_brackets("Egypt", "income")
    income_tax = _apply_brackets(gross_usd, brackets)

    social_rate = _cfg(_ALL_CONFIG, "Egypt", "social", "rate")
    social = gross_usd * social_rate

    return income_tax + social


def _tax_brazil(gross_usd: float) -> float:
    """Brazil income tax + INSS."""
    brackets = _get_brackets("Brazil", "income")
    income_tax = _apply_brackets(gross_usd, brackets)

    inss_rate = _cfg(_ALL_CONFIG, "Brazil", "social", "inss_rate")
    inss_cap = _lc_to_usd(
        _cfg(_ALL_CONFIG, "Brazil", "social", "inss_cap_monthly_lc") * 12, "BRL"
    )
    social = min(gross_usd * inss_rate, inss_cap)

    return income_tax + social


def _tax_mexico(gross_usd: float) -> float:
    """Mexico income tax + IMSS."""
    brackets = _get_brackets("Mexico", "income")
    income_tax = _apply_brackets(gross_usd, brackets)

    social_rate = _cfg(_ALL_CONFIG, "Mexico", "social", "imss_rate")
    social = gross_usd * social_rate

    return income_tax + social


def _tax_chile(gross_usd: float) -> float:
    """Chile income tax + AFP."""
    brackets = _get_brackets("Chile", "income")
    income_tax = _apply_brackets(gross_usd, brackets)

    afp_rate = _cfg(_ALL_CONFIG, "Chile", "social", "afp_rate")
    social = gross_usd * afp_rate

    return income_tax + social


def _tax_colombia(gross_usd: float) -> float:
    """Colombia income tax + social."""
    brackets = _get_brackets("Colombia", "income")
    income_tax = _apply_brackets(gross_usd, brackets)

    social_rate = _cfg(_ALL_CONFIG, "Colombia", "social", "rate")
    social = gross_usd * social_rate

    return income_tax + social


def _tax_pakistan(gross_usd: float) -> float:
    """Pakistan income tax (salaried persons)."""
    brackets = _get_brackets("Pakistan", "income")
    return _apply_brackets(gross_usd, brackets)


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN DISPATCH
# ═══════════════════════════════════════════════════════════════════════════════

_COUNTRY_TAX_FN: dict[str, Callable[[float], float]] = {
    "UK": _tax_uk,
    "Canada": _tax_canada,
    "Germany": _tax_germany,
    "Switzerland": _tax_switzerland,
    "France": _tax_france,
    "Netherlands": _tax_netherlands,
    "India": _tax_india,
    "Australia": _tax_australia,
    "Singapore": _tax_singapore,
    "Hong Kong": _tax_hong_kong,
    "Japan": _tax_japan,
    "South Korea": _tax_south_korea,
    "Israel": _tax_israel,
    "China": _tax_china,
    "Sweden": _tax_sweden,
    "Denmark": _tax_denmark,
    "Norway": _tax_norway,
    "Finland": _tax_finland,
    "Belgium": _tax_belgium,
    "Austria": _tax_austria,
    "Italy": _tax_italy,
    "Spain": _tax_spain,
    "Portugal": _tax_portugal,
    "Poland": _tax_poland,
    "Czech Republic": _tax_czech,
    "Estonia": _tax_estonia,
    "New Zealand": _tax_new_zealand,
    "Taiwan": _tax_taiwan,
    "Saudi Arabia": _tax_saudi_arabia,
    "UAE": _tax_uae,
    "South Africa": _tax_south_africa,
    "Egypt": _tax_egypt,
    "Brazil": _tax_brazil,
    "Mexico": _tax_mexico,
    "Chile": _tax_chile,
    "Colombia": _tax_colombia,
    "Pakistan": _tax_pakistan,
}

# Generic effective rate fallback
_GENERIC_EFFECTIVE_RATE = _cfg(_ALL_CONFIG, "_generic", "income", "effective_rate")


def calculate_annual_tax(
    gross_usd_k: float,
    country: str,
    us_state: Optional[str] = None,
    us_city: Optional[str] = None,
) -> float:
    """
    Calculate annual after-tax income.

    Args:
        gross_usd_k: Gross annual salary in $K USD (e.g., 150 = $150,000)
        country: Country name (must match keys in _COUNTRY_TAX_FN or be "USA")
        us_state: US state code (2-letter) if country is USA
        us_city: US city for city-level taxes (e.g., "NYC")

    Returns:
        After-tax annual income in $K USD
    """
    gross = gross_usd_k * 1000  # Convert to full dollars

    if country == "USA":
        state = us_state or "CA"
        tax = _us_total_tax(gross, state, us_city)
    elif country in _COUNTRY_TAX_FN:
        fn = _COUNTRY_TAX_FN[country]
        tax = fn(gross)
    else:
        # Fallback: generic 30% effective rate
        tax = gross * _GENERIC_EFFECTIVE_RATE

    after_tax = max(0, gross - tax)
    return after_tax / 1000  # Return in $K


def get_effective_tax_rate(
    gross_usd_k: float,
    country: str,
    us_state: Optional[str] = None,
    us_city: Optional[str] = None,
) -> float:
    """Get effective tax rate as a decimal (0-1)."""
    after_tax = calculate_annual_tax(gross_usd_k, country, us_state, us_city)
    if gross_usd_k <= 0:
        return 0.0
    return 1.0 - (after_tax / gross_usd_k)


# ═══════════════════════════════════════════════════════════════════════════════
# VALIDATION
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    # Test with typical tech salaries
    test_cases = [
        ("USA", "CA", "Bay Area", 150),
        ("USA", "NY", "NYC", 150),
        ("USA", "WA", None, 150),
        ("USA", "TX", None, 150),
        ("UK", None, None, 80),
        ("Germany", None, None, 75),
        ("Switzerland", None, None, 130),
        ("Canada", None, None, 90),
        ("India", None, None, 25),
        ("Singapore", None, None, 80),
        ("Hong Kong", None, None, 70),
        ("Australia", None, None, 90),
        ("Japan", None, None, 60),
        ("France", None, None, 65),
        ("Netherlands", None, None, 70),
        ("Pakistan", None, None, 9.5),
        ("UAE", None, None, 80),
        ("Sweden", None, None, 65),
        ("Brazil", None, None, 30),
        ("South Korea", None, None, 55),
    ]

    print(
        f"{'Country':<15} {'State':>5} {'City':<10} {'Gross $K':>9} {'After-Tax':>10} {'Eff Rate':>9}"
    )
    print("-" * 65)
    for country, state, city, gross in test_cases:
        after_tax = calculate_annual_tax(gross, country, state, city)
        rate = get_effective_tax_rate(gross, country, state, city)
        print(
            f"{country:<15} {(state or '-'):>5} {(city or '-'):<10} ${gross:>7.1f}K  ${after_tax:>7.1f}K  {rate:>7.1%}"
        )
