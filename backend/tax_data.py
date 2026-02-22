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
"""

import sqlite3
from pathlib import Path
from typing import Optional

# ─── Database Loading ────────────────────────────────────────────────────────

DB_PATH = Path(__file__).parent / "career_tree.db"


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


# ─── Module-level caches (loaded once at import time) ────────────────────────

FX = _load_exchange_rates()
_ALL_BRACKETS = _load_all_brackets(FX)
_ALL_CONFIG = _load_all_config()


# ─── Helper: get brackets for a country/scope ───────────────────────────────


def _get_brackets(country: str, scope: str) -> list[tuple[float, float]]:
    """Get brackets for a (country, scope) pair from the loaded cache."""
    return _ALL_BRACKETS.get((country, scope), [])


# ─── Exchange rate helper (kept for compatibility with per-country functions) ─


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


# ═════════════════════════════════════════════════════════════════════════════
# US FEDERAL TAX — loaded from DB
# ═════════════════════════════════════════════════════════════════════════════

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


def _us_fica(gross_usd: float) -> float:
    """Calculate FICA taxes (Social Security + Medicare)."""
    ss = min(gross_usd, SS_WAGE_BASE) * SS_RATE
    medicare = gross_usd * MEDICARE_RATE
    if gross_usd > MEDICARE_SURTAX_THRESHOLD:
        medicare += (gross_usd - MEDICARE_SURTAX_THRESHOLD) * MEDICARE_SURTAX_RATE
    return ss + medicare


# ═════════════════════════════════════════════════════════════════════════════
# US STATE TAX — loaded from DB
# ═════════════════════════════════════════════════════════════════════════════

# Build US_STATE_BRACKETS from DB: state_XX scope -> XX key
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


# ═════════════════════════════════════════════════════════════════════════════
# UK TAX (2024/25) — loaded from DB
# ═════════════════════════════════════════════════════════════════════════════

_UK_PERSONAL_ALLOWANCE = _cfg_usd(
    _ALL_CONFIG, FX, "UK", "income", "personal_allowance_lc", "GBP"
)
_UK_PA_TAPER_START = _cfg_usd(
    _ALL_CONFIG, FX, "UK", "income", "pa_taper_start_lc", "GBP"
)

UK_INCOME_BRACKETS = _get_brackets("UK", "income")
UK_NI_BRACKETS = _get_brackets("UK", "national_insurance")


def _uk_tax(gross_usd: float) -> float:
    """UK income tax + National Insurance."""
    # Personal allowance taper: reduced by £1 for every £2 over £100K
    pa = _UK_PERSONAL_ALLOWANCE
    if gross_usd > _UK_PA_TAPER_START:
        reduction = (gross_usd - _UK_PA_TAPER_START) / 2
        pa = max(0, pa - reduction)

    # Income tax with adjusted PA
    brackets = [
        (pa, 0.0),
        (_lc_to_usd(50270, "GBP"), 0.20),
        (_lc_to_usd(125140, "GBP"), 0.40),
        (float("inf"), 0.45),
    ]
    income_tax = _apply_brackets(gross_usd, brackets)
    ni = _apply_brackets(gross_usd, UK_NI_BRACKETS)
    return income_tax + ni


# ═════════════════════════════════════════════════════════════════════════════
# CANADA TAX (2024 — Federal + Ontario as default province) — loaded from DB
# ═════════════════════════════════════════════════════════════════════════════

CA_FEDERAL_BRACKETS = _get_brackets("Canada", "federal")
CA_FEDERAL_PERSONAL = _cfg_usd(
    _ALL_CONFIG, FX, "Canada", "federal", "personal_amount_lc", "CAD"
)

CA_ONTARIO_BRACKETS = _get_brackets("Canada", "provincial_ontario")
CA_ONTARIO_PERSONAL = _cfg_usd(
    _ALL_CONFIG, FX, "Canada", "provincial_ontario", "personal_amount_lc", "CAD"
)

# Ontario surtax thresholds (in local currency, converted at calc time)
_CA_ON_SURTAX_T1_LC = _cfg(
    _ALL_CONFIG, "Canada", "provincial_ontario", "surtax_threshold1_lc"
)
_CA_ON_SURTAX_R1 = _cfg(_ALL_CONFIG, "Canada", "provincial_ontario", "surtax_rate1")
_CA_ON_SURTAX_T2_LC = _cfg(
    _ALL_CONFIG, "Canada", "provincial_ontario", "surtax_threshold2_lc"
)
_CA_ON_SURTAX_R2 = _cfg(_ALL_CONFIG, "Canada", "provincial_ontario", "surtax_rate2")

# Ontario Health Premium max
_CA_OHP_MAX_LC = _cfg(_ALL_CONFIG, "Canada", "provincial_ontario", "ohp_max_lc")

# CPP + EI
CA_CPP_RATE = _cfg(_ALL_CONFIG, "Canada", "social", "cpp_rate")
CA_CPP_MAX = _cfg_usd(_ALL_CONFIG, FX, "Canada", "social", "cpp_max_lc", "CAD")
CA_EI_RATE = _cfg(_ALL_CONFIG, "Canada", "social", "ei_rate")
CA_EI_MAX = _cfg_usd(_ALL_CONFIG, FX, "Canada", "social", "ei_max_lc", "CAD")


def _canada_tax(gross_usd: float) -> float:
    """Canada federal + Ontario provincial + surtax + OHP + CPP/EI."""
    # Federal: apply brackets to full income, then subtract 15% of PA as credit
    federal_gross_tax = _apply_brackets(gross_usd, CA_FEDERAL_BRACKETS)
    federal_credit = CA_FEDERAL_PERSONAL * CA_FEDERAL_BRACKETS[0][1]  # 15% rate
    federal = max(0, federal_gross_tax - federal_credit)

    # Ontario: apply brackets to full income, then subtract 5.05% of PA as credit
    provincial_gross_tax = _apply_brackets(gross_usd, CA_ONTARIO_BRACKETS)
    provincial_credit = CA_ONTARIO_PERSONAL * CA_ONTARIO_BRACKETS[0][1]  # 5.05% rate
    provincial_basic = max(0, provincial_gross_tax - provincial_credit)

    # Ontario surtax: 20% on basic tax > $4,991 + 36% on basic tax > $6,387 (in CAD)
    surtax_t1 = _lc_to_usd(_CA_ON_SURTAX_T1_LC, "CAD")
    surtax_t2 = _lc_to_usd(_CA_ON_SURTAX_T2_LC, "CAD")
    surtax = 0.0
    if provincial_basic > surtax_t1:
        surtax += _CA_ON_SURTAX_R1 * (provincial_basic - surtax_t1)
    if provincial_basic > surtax_t2:
        surtax += _CA_ON_SURTAX_R2 * (provincial_basic - surtax_t2)

    # Ontario Health Premium (simplified: max C$900 for income > C$200K,
    # scales from C$300 at C$20K to C$900 at higher incomes)
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

    cpp = min(gross_usd * CA_CPP_RATE, CA_CPP_MAX)
    ei = min(gross_usd * CA_EI_RATE, CA_EI_MAX)

    return federal + provincial_basic + surtax + ohp_usd + cpp + ei


# ═════════════════════════════════════════════════════════════════════════════
# GERMANY TAX (2024) — loaded from DB
# ═════════════════════════════════════════════════════════════════════════════

DE_BRACKETS = _get_brackets("Germany", "income")

DE_SOCIAL_RATE = _cfg(_ALL_CONFIG, "Germany", "social", "rate")
DE_SOCIAL_CAP = _cfg_usd(_ALL_CONFIG, FX, "Germany", "social", "cap_lc", "EUR")
_DE_SOLI_THRESHOLD_LC = _cfg(_ALL_CONFIG, "Germany", "income", "soli_threshold_lc")
_DE_SOLI_RATE = _cfg(_ALL_CONFIG, "Germany", "income", "soli_rate")


def _germany_tax(gross_usd: float) -> float:
    """Germany income tax + Soli + social contributions."""
    income_tax = _apply_brackets(gross_usd, DE_BRACKETS)
    # Solidaritätszuschlag: 5.5% of income tax (only if tax > €18,130 ~ $19.7K)
    soli_threshold = _lc_to_usd(_DE_SOLI_THRESHOLD_LC, "EUR")
    soli = income_tax * _DE_SOLI_RATE if income_tax > soli_threshold else 0
    social = min(gross_usd, DE_SOCIAL_CAP) * DE_SOCIAL_RATE
    return income_tax + soli + social


# ═════════════════════════════════════════════════════════════════════════════
# SWITZERLAND TAX (2024 — Federal + Zurich cantonal) — loaded from DB
# ═════════════════════════════════════════════════════════════════════════════

CH_FEDERAL_BRACKETS = _get_brackets("Switzerland", "federal")

CH_CANTONAL_EFFECTIVE = _cfg(_ALL_CONFIG, "Switzerland", "cantonal", "effective_rate")
CH_SOCIAL_RATE = _cfg(_ALL_CONFIG, "Switzerland", "social", "rate")
CH_SOCIAL_CAP = _cfg_usd(_ALL_CONFIG, FX, "Switzerland", "social", "cap_lc", "CHF")


def _switzerland_tax(gross_usd: float) -> float:
    """Switzerland federal + cantonal + social contributions."""
    federal = _apply_brackets(gross_usd, CH_FEDERAL_BRACKETS)
    cantonal = gross_usd * CH_CANTONAL_EFFECTIVE
    social = min(gross_usd, CH_SOCIAL_CAP) * CH_SOCIAL_RATE
    return federal + cantonal + social


# ═════════════════════════════════════════════════════════════════════════════
# FRANCE TAX (2024) — loaded from DB
# ═════════════════════════════════════════════════════════════════════════════

FR_BRACKETS = _get_brackets("France", "income")

_FR_PROFESSIONAL_DEDUCTION_RATE = _cfg(
    _ALL_CONFIG, "France", "income", "professional_deduction_rate"
)
FR_SOCIAL_RATE = _cfg(_ALL_CONFIG, "France", "social", "rate")


def _france_tax(gross_usd: float) -> float:
    """France income tax + social contributions."""
    # France applies 10% deduction for professional expenses
    taxable = gross_usd * (1 - _FR_PROFESSIONAL_DEDUCTION_RATE)
    income_tax = _apply_brackets(taxable, FR_BRACKETS)
    social = gross_usd * FR_SOCIAL_RATE
    return income_tax + social


# ═════════════════════════════════════════════════════════════════════════════
# NETHERLANDS TAX (2024) — loaded from DB
# ═════════════════════════════════════════════════════════════════════════════

NL_BRACKETS = _get_brackets("Netherlands", "income")


def _netherlands_tax(gross_usd: float) -> float:
    """Netherlands income tax (includes social contributions in Box 1 rate)."""
    return _apply_brackets(gross_usd, NL_BRACKETS)


# ═════════════════════════════════════════════════════════════════════════════
# INDIA TAX (2024-25 New Tax Regime) — loaded from DB
# ═════════════════════════════════════════════════════════════════════════════

IN_BRACKETS = _get_brackets("India", "income")

_IN_CESS_RATE = _cfg(_ALL_CONFIG, "India", "income", "cess_rate")
IN_EPF_RATE = _cfg(_ALL_CONFIG, "India", "social", "epf_rate")


def _india_tax(gross_usd: float) -> float:
    """India income tax (new regime) + EPF."""
    income_tax = _apply_brackets(gross_usd, IN_BRACKETS)
    # 4% health & education cess on income tax
    cess = income_tax * _IN_CESS_RATE
    epf = gross_usd * IN_EPF_RATE
    return income_tax + cess + epf


# ═════════════════════════════════════════════════════════════════════════════
# AUSTRALIA TAX (2024-25) — loaded from DB
# ═════════════════════════════════════════════════════════════════════════════

AU_BRACKETS = _get_brackets("Australia", "income")

AU_MEDICARE = _cfg(_ALL_CONFIG, "Australia", "social", "medicare_rate")


def _australia_tax(gross_usd: float) -> float:
    """Australia income tax + Medicare levy."""
    income_tax = _apply_brackets(gross_usd, AU_BRACKETS)
    medicare = gross_usd * AU_MEDICARE
    return income_tax + medicare


# ═════════════════════════════════════════════════════════════════════════════
# SINGAPORE TAX (2024) — loaded from DB
# ═════════════════════════════════════════════════════════════════════════════

SG_BRACKETS = _get_brackets("Singapore", "income")

SG_CPF_RATE = _cfg(_ALL_CONFIG, "Singapore", "social", "cpf_rate")
SG_CPF_CAP = (
    _cfg_usd(_ALL_CONFIG, FX, "Singapore", "social", "cpf_cap_monthly_lc", "SGD") * 12
)


def _singapore_tax(gross_usd: float) -> float:
    """Singapore income tax + CPF."""
    income_tax = _apply_brackets(gross_usd, SG_BRACKETS)
    cpf = min(gross_usd, SG_CPF_CAP) * SG_CPF_RATE
    return income_tax + cpf


# ═════════════════════════════════════════════════════════════════════════════
# HONG KONG TAX (2024-25) — loaded from DB
# ═════════════════════════════════════════════════════════════════════════════

HK_BRACKETS = _get_brackets("Hong Kong", "income")

HK_PERSONAL_ALLOWANCE = _cfg_usd(
    _ALL_CONFIG, FX, "Hong Kong", "income", "personal_allowance_lc", "HKD"
)
HK_STANDARD_RATE = _cfg(_ALL_CONFIG, "Hong Kong", "income", "standard_rate")
HK_MPF_RATE = _cfg(_ALL_CONFIG, "Hong Kong", "social", "mpf_rate")
HK_MPF_CAP = (
    _cfg_usd(_ALL_CONFIG, FX, "Hong Kong", "social", "mpf_cap_monthly_lc", "HKD") * 12
)


def _hong_kong_tax(gross_usd: float) -> float:
    """Hong Kong salaries tax + MPF."""
    # Progressive tax on income after allowance
    taxable = max(0, gross_usd - HK_PERSONAL_ALLOWANCE)
    progressive = _apply_brackets(taxable, HK_BRACKETS)
    # Standard rate cap
    standard = gross_usd * HK_STANDARD_RATE
    income_tax = min(progressive, standard)
    mpf = min(gross_usd, HK_MPF_CAP) * HK_MPF_RATE
    return income_tax + mpf


# ═════════════════════════════════════════════════════════════════════════════
# JAPAN TAX (2024) — loaded from DB
# ═════════════════════════════════════════════════════════════════════════════

JP_BRACKETS = _get_brackets("Japan", "income")

JP_RESIDENT_TAX = _cfg(_ALL_CONFIG, "Japan", "income", "resident_tax_rate")
_JP_RECONSTRUCTION_SURTAX = _cfg(
    _ALL_CONFIG, "Japan", "income", "reconstruction_surtax_rate"
)
_JP_EMP_DEDUCTION_LOW_LC = _cfg(
    _ALL_CONFIG, "Japan", "income", "employment_deduction_low_lc"
)
_JP_EMP_DEDUCTION_MID_ADD_LC = _cfg(
    _ALL_CONFIG, "Japan", "income", "employment_deduction_mid_add_lc"
)
_JP_EMP_DEDUCTION_MID_RATE = _cfg(
    _ALL_CONFIG, "Japan", "income", "employment_deduction_mid_rate"
)
_JP_EMP_DEDUCTION_HIGH_LC = _cfg(
    _ALL_CONFIG, "Japan", "income", "employment_deduction_high_lc"
)
_JP_EMP_DEDUCTION_LOW_THRESHOLD_LC = _cfg(
    _ALL_CONFIG, "Japan", "income", "employment_deduction_low_threshold_lc"
)
_JP_EMP_DEDUCTION_HIGH_THRESHOLD_LC = _cfg(
    _ALL_CONFIG, "Japan", "income", "employment_deduction_high_threshold_lc"
)
JP_SOCIAL_RATE = _cfg(_ALL_CONFIG, "Japan", "social", "rate")
JP_SOCIAL_CAP = (
    _cfg_usd(_ALL_CONFIG, FX, "Japan", "social", "cap_monthly_lc", "JPY") * 12
)
JP_BASIC_EXEMPTION_LC = _cfg(_ALL_CONFIG, "Japan", "income", "basic_exemption_lc")


def _japan_tax(gross_usd: float) -> float:
    """Japan income tax + resident tax + social insurance."""
    # 1. Social insurance (employee share: pension ~9.15%, health ~5%, emp ins ~0.3%)
    social = min(gross_usd, JP_SOCIAL_CAP) * JP_SOCIAL_RATE

    # 2. Employment income deduction (simplified 3-tier formula)
    if gross_usd < _lc_to_usd(_JP_EMP_DEDUCTION_LOW_THRESHOLD_LC, "JPY"):
        emp_deduction = _lc_to_usd(_JP_EMP_DEDUCTION_LOW_LC, "JPY")
    elif gross_usd < _lc_to_usd(_JP_EMP_DEDUCTION_HIGH_THRESHOLD_LC, "JPY"):
        emp_deduction = gross_usd * _JP_EMP_DEDUCTION_MID_RATE + _lc_to_usd(
            _JP_EMP_DEDUCTION_MID_ADD_LC, "JPY"
        )
    else:
        emp_deduction = _lc_to_usd(_JP_EMP_DEDUCTION_HIGH_LC, "JPY")

    # 3. Taxable income = gross - emp deduction - social - basic exemption (¥480K)
    basic_exemption = _lc_to_usd(JP_BASIC_EXEMPTION_LC, "JPY")
    taxable = max(0, gross_usd - emp_deduction - social - basic_exemption)

    # 4. National income tax + reconstruction surtax 2.1%
    income_tax = _apply_brackets(taxable, JP_BRACKETS)
    income_tax *= 1 + _JP_RECONSTRUCTION_SURTAX

    # 5. Resident tax (municipal + prefectural) ~10% on same taxable base
    resident = taxable * JP_RESIDENT_TAX

    return income_tax + resident + social


# ═════════════════════════════════════════════════════════════════════════════
# SOUTH KOREA TAX (2024) — loaded from DB
# ═════════════════════════════════════════════════════════════════════════════

KR_BRACKETS = _get_brackets("South Korea", "income")

_KR_LOCAL_TAX_RATE = _cfg(_ALL_CONFIG, "South Korea", "income", "local_tax_rate")
KR_SOCIAL_RATE = _cfg(_ALL_CONFIG, "South Korea", "social", "rate")
KR_SOCIAL_CAP = (
    _cfg_usd(_ALL_CONFIG, FX, "South Korea", "social", "cap_monthly_lc", "KRW") * 12
)


def _south_korea_tax(gross_usd: float) -> float:
    """South Korea income + local + social."""
    income_tax = _apply_brackets(gross_usd, KR_BRACKETS)
    local_tax = income_tax * _KR_LOCAL_TAX_RATE
    social = min(gross_usd, KR_SOCIAL_CAP) * KR_SOCIAL_RATE
    return income_tax + local_tax + social


# ═════════════════════════════════════════════════════════════════════════════
# ISRAEL TAX (2024) — loaded from DB
# ═════════════════════════════════════════════════════════════════════════════

IL_BRACKETS = _get_brackets("Israel", "income")

IL_SOCIAL_RATE = _cfg(_ALL_CONFIG, "Israel", "social", "rate")


def _israel_tax(gross_usd: float) -> float:
    """Israel income tax + National Insurance + Health."""
    income_tax = _apply_brackets(gross_usd, IL_BRACKETS)
    social = gross_usd * IL_SOCIAL_RATE
    return income_tax + social


# ═════════════════════════════════════════════════════════════════════════════
# CHINA TAX (2024) — loaded from DB
# ═════════════════════════════════════════════════════════════════════════════

CN_BRACKETS = _get_brackets("China", "income")

CN_STANDARD_DEDUCTION = _cfg_usd(
    _ALL_CONFIG, FX, "China", "income", "standard_deduction_lc", "CNY"
)
CN_SOCIAL_RATE = _cfg(_ALL_CONFIG, "China", "social", "rate")
CN_SOCIAL_CAP = _cfg_usd(_ALL_CONFIG, FX, "China", "social", "cap_lc", "CNY")


def _china_tax(gross_usd: float) -> float:
    """China IIT + social insurance."""
    social = min(gross_usd, CN_SOCIAL_CAP) * CN_SOCIAL_RATE
    taxable = max(0, gross_usd - CN_STANDARD_DEDUCTION - social)
    income_tax = _apply_brackets(taxable, CN_BRACKETS)
    return income_tax + social


# ═════════════════════════════════════════════════════════════════════════════
# SCANDINAVIAN COUNTRIES — loaded from DB
# ═════════════════════════════════════════════════════════════════════════════

# Sweden config
_SE_MUNICIPAL_RATE = _cfg(_ALL_CONFIG, "Sweden", "income", "municipal_rate")
_SE_STATE_THRESHOLD_LC = _cfg(_ALL_CONFIG, "Sweden", "income", "state_threshold_lc")
_SE_STATE_RATE = _cfg(_ALL_CONFIG, "Sweden", "income", "state_rate")
_SE_PENSION_RATE = _cfg(_ALL_CONFIG, "Sweden", "social", "pension_rate")
_SE_PENSION_CAP_LC = _cfg(_ALL_CONFIG, "Sweden", "social", "pension_cap_lc")


def _sweden_tax(gross_usd: float) -> float:
    municipal_rate = _SE_MUNICIPAL_RATE
    state_threshold = _lc_to_usd(_SE_STATE_THRESHOLD_LC, "SEK")
    state_rate = _SE_STATE_RATE

    tax = gross_usd * municipal_rate
    if gross_usd > state_threshold:
        tax += (gross_usd - state_threshold) * state_rate
    # Social: employee pension ~7% (capped)
    social = min(gross_usd, _lc_to_usd(_SE_PENSION_CAP_LC, "SEK")) * _SE_PENSION_RATE
    return tax + social


# Denmark config
_DK_AM_BIDRAG_RATE = _cfg(_ALL_CONFIG, "Denmark", "income", "am_bidrag_rate")
_DK_PERSONAL_ALLOWANCE_LC = _cfg(
    _ALL_CONFIG, "Denmark", "income", "personal_allowance_lc"
)
_DK_MUNICIPAL_RATE = _cfg(_ALL_CONFIG, "Denmark", "income", "municipal_rate")
_DK_STATE_BOTTOM_RATE = _cfg(_ALL_CONFIG, "Denmark", "income", "state_bottom_rate")
_DK_TOP_THRESHOLD_LC = _cfg(_ALL_CONFIG, "Denmark", "income", "top_threshold_lc")
_DK_TOP_RATE = _cfg(_ALL_CONFIG, "Denmark", "income", "top_rate")
_DK_TAX_CEILING = _cfg(_ALL_CONFIG, "Denmark", "income", "tax_ceiling")
_DK_ATP_ANNUAL_LC = _cfg(_ALL_CONFIG, "Denmark", "social", "atp_annual_lc")


def _denmark_tax(gross_usd: float) -> float:
    # AM-bidrag (labor market contribution): 8%
    am = gross_usd * _DK_AM_BIDRAG_RATE
    taxable = gross_usd - am
    personal_allowance = _lc_to_usd(_DK_PERSONAL_ALLOWANCE_LC, "DKK")
    taxable = max(0, taxable - personal_allowance)
    # Municipal + church + health: ~25%
    # State: bottom bracket 12.09%, top bracket 15% above DKK 588,900
    municipal = taxable * _DK_MUNICIPAL_RATE
    state_bottom = taxable * _DK_STATE_BOTTOM_RATE
    top_threshold = _lc_to_usd(_DK_TOP_THRESHOLD_LC, "DKK")
    state_top = max(0, taxable - top_threshold) * _DK_TOP_RATE
    # Tax ceiling ~52.07% (effective cap)
    income_tax = min(municipal + state_bottom + state_top, taxable * _DK_TAX_CEILING)
    # ATP (labor market pension): ~DKK 3,408/yr
    atp = _lc_to_usd(_DK_ATP_ANNUAL_LC, "DKK")
    return am + income_tax + atp


# Norway config
_NO_FLAT_RATE = _cfg(_ALL_CONFIG, "Norway", "income", "flat_rate")
_NO_PERSONAL_ALLOWANCE_LC = _cfg(
    _ALL_CONFIG, "Norway", "income", "personal_allowance_lc"
)
_NO_SOCIAL_RATE = _cfg(_ALL_CONFIG, "Norway", "social", "rate")

# Norway trinnskatt brackets from DB
_NO_TRINNSKATT_BRACKETS = _get_brackets("Norway", "trinnskatt")


def _norway_tax(gross_usd: float) -> float:
    # Bracket tax (trinnskatt)
    trinnskatt = _apply_brackets(gross_usd, _NO_TRINNSKATT_BRACKETS)
    # Flat tax on ordinary income: 22%
    personal_allowance = _lc_to_usd(_NO_PERSONAL_ALLOWANCE_LC, "NOK")
    taxable = max(0, gross_usd - personal_allowance)
    flat_tax = taxable * _NO_FLAT_RATE
    # Social: employee ~7.9%
    social = gross_usd * _NO_SOCIAL_RATE
    return trinnskatt + flat_tax + social


# Finland config
_FI_BRACKETS = _get_brackets("Finland", "income")
_FI_MUNICIPAL_RATE = _cfg(_ALL_CONFIG, "Finland", "income", "municipal_rate")
_FI_SOCIAL_RATE = _cfg(_ALL_CONFIG, "Finland", "social", "rate")


def _finland_tax(gross_usd: float) -> float:
    state_tax = _apply_brackets(gross_usd, _FI_BRACKETS)
    # Municipal tax: ~20% (average)
    municipal = gross_usd * _FI_MUNICIPAL_RATE
    # Social: pension ~7.15% + unemployment ~1.5% + health ~1.96% = ~10.6%
    social = gross_usd * _FI_SOCIAL_RATE
    return state_tax + municipal + social


# ═════════════════════════════════════════════════════════════════════════════
# BELGIUM TAX (2024) — loaded from DB
# ═════════════════════════════════════════════════════════════════════════════

_BE_BRACKETS = _get_brackets("Belgium", "income")
_BE_PERSONAL_ALLOWANCE_LC = _cfg(
    _ALL_CONFIG, "Belgium", "income", "personal_allowance_lc"
)
_BE_MUNICIPAL_SURCHARGE_RATE = _cfg(
    _ALL_CONFIG, "Belgium", "income", "municipal_surcharge_rate"
)
_BE_SOCIAL_RATE = _cfg(_ALL_CONFIG, "Belgium", "social", "rate")


def _belgium_tax(gross_usd: float) -> float:
    personal_allowance = _lc_to_usd(_BE_PERSONAL_ALLOWANCE_LC, "EUR")
    taxable = max(0, gross_usd - personal_allowance)
    income_tax = _apply_brackets(taxable, _BE_BRACKETS)
    # Municipal surcharge: ~7% of income tax
    municipal = income_tax * _BE_MUNICIPAL_SURCHARGE_RATE
    # Social: ~13.07% of gross
    social = gross_usd * _BE_SOCIAL_RATE
    return income_tax + municipal + social


# ═════════════════════════════════════════════════════════════════════════════
# AUSTRIA TAX (2024) — loaded from DB
# ═════════════════════════════════════════════════════════════════════════════

_AT_BRACKETS = _get_brackets("Austria", "income")
_AT_SOCIAL_RATE = _cfg(_ALL_CONFIG, "Austria", "social", "rate")
_AT_SOCIAL_CAP_LC = _cfg(_ALL_CONFIG, "Austria", "social", "cap_lc")


def _austria_tax(gross_usd: float) -> float:
    income_tax = _apply_brackets(gross_usd, _AT_BRACKETS)
    # Social: ~18.12% (pension 10.25% + health 3.87% + unemployment 3% + other 1%)
    social = min(gross_usd, _lc_to_usd(_AT_SOCIAL_CAP_LC, "EUR")) * _AT_SOCIAL_RATE
    return income_tax + social


# ═════════════════════════════════════════════════════════════════════════════
# ITALY TAX (2024) — loaded from DB
# ═════════════════════════════════════════════════════════════════════════════

_IT_BRACKETS = _get_brackets("Italy", "income")
_IT_SURCHARGE_RATE = _cfg(_ALL_CONFIG, "Italy", "income", "surcharge_rate")
_IT_SOCIAL_RATE = _cfg(_ALL_CONFIG, "Italy", "social", "rate")


def _italy_tax(gross_usd: float) -> float:
    income_tax = _apply_brackets(gross_usd, _IT_BRACKETS)
    # Regional + municipal surcharge: ~2-3%
    surcharge = gross_usd * _IT_SURCHARGE_RATE
    # Social: ~9.19% employee
    social = gross_usd * _IT_SOCIAL_RATE
    return income_tax + surcharge + social


# ═════════════════════════════════════════════════════════════════════════════
# SPAIN TAX (2024) — loaded from DB
# ═════════════════════════════════════════════════════════════════════════════

_ES_BRACKETS = _get_brackets("Spain", "income")
_ES_PERSONAL_ALLOWANCE_LC = _cfg(
    _ALL_CONFIG, "Spain", "income", "personal_allowance_lc"
)
_ES_SOCIAL_RATE = _cfg(_ALL_CONFIG, "Spain", "social", "rate")
_ES_SOCIAL_CAP_LC = _cfg(_ALL_CONFIG, "Spain", "social", "cap_lc")


def _spain_tax(gross_usd: float) -> float:
    personal_allowance = _lc_to_usd(_ES_PERSONAL_ALLOWANCE_LC, "EUR")
    taxable = max(0, gross_usd - personal_allowance)
    income_tax = _apply_brackets(taxable, _ES_BRACKETS)
    # Social: ~6.35% employee
    social = min(gross_usd, _lc_to_usd(_ES_SOCIAL_CAP_LC, "EUR")) * _ES_SOCIAL_RATE
    return income_tax + social


# ═════════════════════════════════════════════════════════════════════════════
# PORTUGAL TAX (2024) — loaded from DB
# ═════════════════════════════════════════════════════════════════════════════

_PT_BRACKETS = _get_brackets("Portugal", "income")
_PT_SOCIAL_RATE = _cfg(_ALL_CONFIG, "Portugal", "social", "rate")


def _portugal_tax(gross_usd: float) -> float:
    income_tax = _apply_brackets(gross_usd, _PT_BRACKETS)
    # Social: 11% employee
    social = gross_usd * _PT_SOCIAL_RATE
    return income_tax + social


# ═════════════════════════════════════════════════════════════════════════════
# EASTERN EUROPE — loaded from DB
# ═════════════════════════════════════════════════════════════════════════════

# Poland
_PL_BRACKETS = _get_brackets("Poland", "income")
_PL_PERSONAL_ALLOWANCE_LC = _cfg(
    _ALL_CONFIG, "Poland", "income", "personal_allowance_lc"
)
_PL_SOCIAL_RATE = _cfg(_ALL_CONFIG, "Poland", "social", "rate")
_PL_SOCIAL_CAP_LC = _cfg(_ALL_CONFIG, "Poland", "social", "cap_lc")
_PL_HEALTH_RATE = _cfg(_ALL_CONFIG, "Poland", "social", "health_rate")


def _poland_tax(gross_usd: float) -> float:
    personal_allowance = _lc_to_usd(_PL_PERSONAL_ALLOWANCE_LC, "PLN")
    taxable = max(0, gross_usd - personal_allowance)
    income_tax = _apply_brackets(taxable, _PL_BRACKETS)
    # Social: ~13.71% (pension 9.76% + disability 1.5% + sickness 2.45%)
    social = min(gross_usd, _lc_to_usd(_PL_SOCIAL_CAP_LC, "PLN")) * _PL_SOCIAL_RATE
    # Health: 9% of (gross - social)
    health = (gross_usd - social) * _PL_HEALTH_RATE
    return income_tax + social + health


# Czech Republic
_CZ_BRACKETS = _get_brackets("Czech Republic", "income")
_CZ_SOCIAL_RATE = _cfg(_ALL_CONFIG, "Czech Republic", "social", "rate")


def _czech_tax(gross_usd: float) -> float:
    # The brackets from DB already encode the 15%/23% split
    # But the original code used threshold-based logic, not _apply_brackets.
    # To keep exact same behavior: use the bracket thresholds directly.
    if _CZ_BRACKETS:
        threshold = _CZ_BRACKETS[0][0]  # First bracket threshold (in USD already)
        if gross_usd <= threshold:
            income_tax = gross_usd * 0.15
        else:
            income_tax = threshold * 0.15 + (gross_usd - threshold) * 0.23
    else:
        income_tax = gross_usd * 0.15
    # Social + health: ~11% employee (6.5% social + 4.5% health)
    social = gross_usd * _CZ_SOCIAL_RATE
    return income_tax + social


# Estonia
_EE_BRACKETS = _get_brackets("Estonia", "income")
_EE_SOCIAL_RATE = _cfg(_ALL_CONFIG, "Estonia", "social", "rate")


def _estonia_tax(gross_usd: float) -> float:
    # Flat 20% above basic exemption — brackets encode this
    # Original: basic_exemption from bracket[0], then flat 20% above
    if _EE_BRACKETS:
        basic_exemption = _EE_BRACKETS[0][0]  # First threshold = exemption
        taxable = max(0, gross_usd - basic_exemption)
        income_tax = taxable * 0.20
    else:
        income_tax = gross_usd * 0.20
    # Social: employee pays only unemployment 1.6%; pension 2%
    social = gross_usd * _EE_SOCIAL_RATE
    return income_tax + social


# ═════════════════════════════════════════════════════════════════════════════
# ASIA-PACIFIC (remaining) — loaded from DB
# ═════════════════════════════════════════════════════════════════════════════

# New Zealand
_NZ_BRACKETS = _get_brackets("New Zealand", "income")
_NZ_ACC_RATE = _cfg(_ALL_CONFIG, "New Zealand", "social", "acc_rate")


def _new_zealand_tax(gross_usd: float) -> float:
    income_tax = _apply_brackets(gross_usd, _NZ_BRACKETS)
    # ACC levy: ~1.6%
    acc = gross_usd * _NZ_ACC_RATE
    return income_tax + acc


# Taiwan
_TW_BRACKETS = _get_brackets("Taiwan", "income")
_TW_STANDARD_DEDUCTION_LC = _cfg(
    _ALL_CONFIG, "Taiwan", "income", "standard_deduction_lc"
)
_TW_SOCIAL_RATE = _cfg(_ALL_CONFIG, "Taiwan", "social", "rate")


def _taiwan_tax(gross_usd: float) -> float:
    standard_deduction = _lc_to_usd(_TW_STANDARD_DEDUCTION_LC, "TWD")
    taxable = max(0, gross_usd - standard_deduction)
    income_tax = _apply_brackets(taxable, _TW_BRACKETS)
    # NHI + Labor insurance: ~3.5%
    social = gross_usd * _TW_SOCIAL_RATE
    return income_tax + social


# ═════════════════════════════════════════════════════════════════════════════
# MIDDLE EAST / AFRICA — loaded from DB
# ═════════════════════════════════════════════════════════════════════════════

_SA_GOSI_RATE = _cfg(_ALL_CONFIG, "Saudi Arabia", "social", "gosi_rate")


def _saudi_arabia_tax(gross_usd: float) -> float:
    """Saudi Arabia: 0% income tax for employees. GOSI ~9.75%."""
    return gross_usd * _SA_GOSI_RATE


def _uae_tax(gross_usd: float) -> float:
    """UAE: 0% income tax, no social contributions for expats."""
    return 0.0


# South Africa
_ZA_BRACKETS = _get_brackets("South Africa", "income")
_ZA_PRIMARY_REBATE_LC = _cfg(_ALL_CONFIG, "South Africa", "income", "primary_rebate_lc")
_ZA_UIF_RATE = _cfg(_ALL_CONFIG, "South Africa", "social", "uif_rate")
_ZA_UIF_CAP_MONTHLY_LC = _cfg(
    _ALL_CONFIG, "South Africa", "social", "uif_cap_monthly_lc"
)


def _south_africa_tax(gross_usd: float) -> float:
    # Primary rebate
    rebate = _lc_to_usd(_ZA_PRIMARY_REBATE_LC, "ZAR")
    income_tax = max(0, _apply_brackets(gross_usd, _ZA_BRACKETS) - rebate)
    # UIF: 1% of gross (capped)
    uif = min(gross_usd * _ZA_UIF_RATE, _lc_to_usd(_ZA_UIF_CAP_MONTHLY_LC * 12, "ZAR"))
    return income_tax + uif


# Egypt
_EG_BRACKETS = _get_brackets("Egypt", "income")
_EG_SOCIAL_RATE = _cfg(_ALL_CONFIG, "Egypt", "social", "rate")


def _egypt_tax(gross_usd: float) -> float:
    income_tax = _apply_brackets(gross_usd, _EG_BRACKETS)
    # Social: ~11% employee
    social = gross_usd * _EG_SOCIAL_RATE
    return income_tax + social


# ═════════════════════════════════════════════════════════════════════════════
# LATIN AMERICA — loaded from DB
# ═════════════════════════════════════════════════════════════════════════════

# Brazil
_BR_BRACKETS = _get_brackets("Brazil", "income")
_BR_INSS_RATE = _cfg(_ALL_CONFIG, "Brazil", "social", "inss_rate")
_BR_INSS_CAP_MONTHLY_LC = _cfg(_ALL_CONFIG, "Brazil", "social", "inss_cap_monthly_lc")


def _brazil_tax(gross_usd: float) -> float:
    income_tax = _apply_brackets(gross_usd, _BR_BRACKETS)
    # Social: INSS ~11% (capped) + FGTS is employer-only
    social = min(
        gross_usd * _BR_INSS_RATE, _lc_to_usd(_BR_INSS_CAP_MONTHLY_LC * 12, "BRL")
    )
    return income_tax + social


# Mexico
_MX_BRACKETS = _get_brackets("Mexico", "income")
_MX_SOCIAL_RATE = _cfg(_ALL_CONFIG, "Mexico", "social", "imss_rate")


def _mexico_tax(gross_usd: float) -> float:
    income_tax = _apply_brackets(gross_usd, _MX_BRACKETS)
    # Social: IMSS ~3% employee
    social = gross_usd * _MX_SOCIAL_RATE
    return income_tax + social


# Chile
_CL_BRACKETS = _get_brackets("Chile", "income")
_CL_AFP_RATE = _cfg(_ALL_CONFIG, "Chile", "social", "afp_rate")


def _chile_tax(gross_usd: float) -> float:
    income_tax = _apply_brackets(gross_usd, _CL_BRACKETS)
    # AFP pension: ~12.5% employee (including commission)
    social = gross_usd * _CL_AFP_RATE
    return income_tax + social


# Colombia
_CO_BRACKETS = _get_brackets("Colombia", "income")
_CO_SOCIAL_RATE = _cfg(_ALL_CONFIG, "Colombia", "social", "rate")


def _colombia_tax(gross_usd: float) -> float:
    income_tax = _apply_brackets(gross_usd, _CO_BRACKETS)
    # Social: pension 4% + health 4% = 8%
    social = gross_usd * _CO_SOCIAL_RATE
    return income_tax + social


# ═════════════════════════════════════════════════════════════════════════════
# PAKISTAN TAX (2024-25) — for baseline calculation, loaded from DB
# ═════════════════════════════════════════════════════════════════════════════

PK_BRACKETS = _get_brackets("Pakistan", "income")


def _pakistan_tax(gross_usd: float) -> float:
    """Pakistan income tax (salaried persons)."""
    return _apply_brackets(gross_usd, PK_BRACKETS)


# ═════════════════════════════════════════════════════════════════════════════
# MAIN DISPATCH
# ═════════════════════════════════════════════════════════════════════════════

_COUNTRY_TAX_FN = {
    "USA": None,  # Handled specially (needs state)
    "UK": _uk_tax,
    "Canada": _canada_tax,
    "Germany": _germany_tax,
    "Switzerland": _switzerland_tax,
    "France": _france_tax,
    "Netherlands": _netherlands_tax,
    "India": _india_tax,
    "Australia": _australia_tax,
    "Singapore": _singapore_tax,
    "Hong Kong": _hong_kong_tax,
    "Japan": _japan_tax,
    "South Korea": _south_korea_tax,
    "Israel": _israel_tax,
    "China": _china_tax,
    "Sweden": _sweden_tax,
    "Denmark": _denmark_tax,
    "Norway": _norway_tax,
    "Finland": _finland_tax,
    "Belgium": _belgium_tax,
    "Austria": _austria_tax,
    "Italy": _italy_tax,
    "Spain": _spain_tax,
    "Portugal": _portugal_tax,
    "Poland": _poland_tax,
    "Czech Republic": _czech_tax,
    "Estonia": _estonia_tax,
    "New Zealand": _new_zealand_tax,
    "Taiwan": _taiwan_tax,
    "Saudi Arabia": _saudi_arabia_tax,
    "UAE": _uae_tax,
    "South Africa": _south_africa_tax,
    "Egypt": _egypt_tax,
    "Brazil": _brazil_tax,
    "Mexico": _mexico_tax,
    "Chile": _chile_tax,
    "Colombia": _colombia_tax,
    "Pakistan": _pakistan_tax,
}

# Countries not listed above — use a generic ~30% effective rate
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
        country: Country name (must match keys in _COUNTRY_TAX_FN)
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


# ═════════════════════════════════════════════════════════════════════════════
# VALIDATION
# ═════════════════════════════════════════════════════════════════════════════

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
