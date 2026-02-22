"""
Import Reference Data into Database
====================================
Populates the reference data tables (exchange_rates, tax_brackets, tax_config,
living_costs, country_default_cities, market_mappings, us_region_states)
from the existing hardcoded Python data.

Run once after creating the new tables:
    python3 import_reference_data.py
"""

import sqlite3

from config import DB_PATH, get_logger

logger = get_logger(__name__)


def import_all():
    """Import all reference data into the database."""
    # First ensure tables exist
    from database import create_database

    create_database()

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    _import_exchange_rates(cursor)
    _import_tax_brackets(cursor)
    _import_tax_config(cursor)
    _import_living_costs(cursor)
    _import_country_default_cities(cursor)
    _import_market_mappings(cursor)
    _import_us_region_states(cursor)

    conn.commit()
    conn.close()
    logger.info("All reference data imported successfully.")


# ═════════════════════════════════════════════════════════════════════════════
# EXCHANGE RATES
# ═════════════════════════════════════════════════════════════════════════════


def _import_exchange_rates(cursor):
    """Import exchange rates (local currency per 1 USD)."""
    rates = {
        "GBP": (0.79, "UK"),
        "EUR": (0.92, "Eurozone"),
        "CAD": (1.36, "Canada"),
        "CHF": (0.82, "Switzerland"),
        "AUD": (1.53, "Australia"),
        "NZD": (1.63, "New Zealand"),
        "INR": (83.5, "India"),
        "SGD": (1.34, "Singapore"),
        "HKD": (7.82, "Hong Kong"),
        "JPY": (151.0, "Japan"),
        "KRW": (1430.0, "South Korea"),
        "ILS": (3.65, "Israel"),
        "CNY": (7.24, "China"),
        "SEK": (10.5, "Sweden"),
        "DKK": (6.88, "Denmark"),
        "NOK": (10.7, "Norway"),
        "BRL": (5.9, "Brazil"),
        "MXN": (20.0, "Mexico"),
        "ZAR": (16.5, "South Africa"),
        "CLP": (950.0, "Chile"),
        "COP": (4300.0, "Colombia"),
        "TWD": (31.5, "Taiwan"),
        "PLN": (4.0, "Poland"),
        "CZK": (23.0, "Czech Republic"),
        "PKR": (278.0, "Pakistan"),
        "EGP": (48.0, "Egypt"),
        "SAR": (3.75, "Saudi Arabia"),
        "AED": (3.67, "UAE"),
        "USD": (1.0, "USA"),
    }

    cursor.execute("DELETE FROM exchange_rates")
    for currency, (rate, country) in rates.items():
        cursor.execute(
            "INSERT INTO exchange_rates (currency, rate_per_usd, country_name) VALUES (?, ?, ?)",
            (currency, rate, country),
        )
    logger.info("Imported %d exchange rates", len(rates))


# ═════════════════════════════════════════════════════════════════════════════
# TAX BRACKETS
# ═════════════════════════════════════════════════════════════════════════════


def _import_tax_brackets(cursor):
    """Import all tax brackets for all countries/scopes."""
    cursor.execute("DELETE FROM tax_brackets")
    count = 0

    # Helper to insert brackets
    def insert_brackets(country, scope, brackets, currency="USD"):
        nonlocal count
        for i, (threshold, rate) in enumerate(brackets):
            # Use a large number instead of infinity for DB storage
            t = threshold if threshold != float("inf") else 999999999999
            cursor.execute(
                "INSERT INTO tax_brackets (country, scope, bracket_order, threshold_lc, rate, currency) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (country, scope, i + 1, t, rate, currency),
            )
            count += 1

    # ── US Federal ───────────────────────────────────────────────────────
    insert_brackets(
        "USA",
        "federal",
        [
            (11600, 0.10),
            (47150, 0.12),
            (100525, 0.22),
            (191950, 0.24),
            (243725, 0.32),
            (609350, 0.35),
            (float("inf"), 0.37),
        ],
    )

    # ── US State brackets ────────────────────────────────────────────────
    us_states = {
        "CA": [
            (10412, 0.01),
            (24684, 0.02),
            (38959, 0.04),
            (54081, 0.06),
            (68350, 0.08),
            (349137, 0.093),
            (418961, 0.103),
            (698271, 0.113),
            (float("inf"), 0.123),
        ],
        "NY": [
            (8500, 0.04),
            (11700, 0.045),
            (13900, 0.0525),
            (80650, 0.0585),
            (215400, 0.0625),
            (1077550, 0.0685),
            (5000000, 0.0965),
            (25000000, 0.103),
            (float("inf"), 0.109),
        ],
        "MA": [(float("inf"), 0.05)],
        "IL": [(float("inf"), 0.0495)],
        "PA": [(float("inf"), 0.0307)],
        "NJ": [
            (20000, 0.014),
            (35000, 0.0175),
            (40000, 0.035),
            (75000, 0.05525),
            (500000, 0.0637),
            (1000000, 0.0897),
            (float("inf"), 0.1075),
        ],
        "MD": [
            (1000, 0.02),
            (2000, 0.03),
            (3000, 0.04),
            (100000, 0.0475),
            (125000, 0.05),
            (150000, 0.0525),
            (250000, 0.055),
            (float("inf"), 0.0575),
        ],
        "DC": [
            (10000, 0.04),
            (40000, 0.06),
            (60000, 0.065),
            (250000, 0.085),
            (500000, 0.0925),
            (1000000, 0.0975),
            (float("inf"), 0.1075),
        ],
        "GA": [
            (750, 0.01),
            (2250, 0.02),
            (3750, 0.03),
            (5250, 0.04),
            (7000, 0.05),
            (float("inf"), 0.055),
        ],
        "TX": [],  # No state income tax
        "WA": [],  # No state income tax
    }
    for state, brackets in us_states.items():
        if brackets:
            insert_brackets("USA", f"state_{state}", brackets)

    # NYC city tax
    insert_brackets(
        "USA",
        "city_NYC",
        [
            (12000, 0.03078),
            (25000, 0.03762),
            (50000, 0.03819),
            (float("inf"), 0.03876),
        ],
    )

    # ── UK ────────────────────────────────────────────────────────────────
    insert_brackets(
        "UK",
        "income",
        [
            (12570, 0.0),
            (50270, 0.20),
            (125140, 0.40),
            (float("inf"), 0.45),
        ],
        "GBP",
    )
    insert_brackets(
        "UK",
        "national_insurance",
        [
            (12570, 0.0),
            (50270, 0.08),
            (float("inf"), 0.02),
        ],
        "GBP",
    )

    # ── Canada ────────────────────────────────────────────────────────────
    insert_brackets(
        "Canada",
        "federal",
        [
            (55867, 0.15),
            (111733, 0.205),
            (154906, 0.26),
            (220000, 0.29),
            (float("inf"), 0.33),
        ],
        "CAD",
    )
    insert_brackets(
        "Canada",
        "provincial_ontario",
        [
            (51446, 0.0505),
            (102894, 0.0915),
            (150000, 0.1116),
            (220000, 0.1216),
            (float("inf"), 0.1316),
        ],
        "CAD",
    )

    # ── Germany ───────────────────────────────────────────────────────────
    insert_brackets(
        "Germany",
        "income",
        [
            (11604, 0.0),
            (17005, 0.14),
            (66760, 0.24),
            (277825, 0.42),
            (float("inf"), 0.45),
        ],
        "EUR",
    )

    # ── Switzerland ───────────────────────────────────────────────────────
    insert_brackets(
        "Switzerland",
        "federal",
        [
            (14500, 0.0),
            (31600, 0.0077),
            (41400, 0.0088),
            (55200, 0.0264),
            (72500, 0.0297),
            (78100, 0.0522),
            (103600, 0.066),
            (134600, 0.088),
            (176000, 0.11),
            (755200, 0.13),
            (float("inf"), 0.115),
        ],
        "CHF",
    )

    # ── France ────────────────────────────────────────────────────────────
    insert_brackets(
        "France",
        "income",
        [
            (11294, 0.0),
            (28797, 0.11),
            (82341, 0.30),
            (177106, 0.41),
            (float("inf"), 0.45),
        ],
        "EUR",
    )

    # ── Netherlands ───────────────────────────────────────────────────────
    insert_brackets(
        "Netherlands",
        "income",
        [
            (75518, 0.3693),
            (float("inf"), 0.495),
        ],
        "EUR",
    )

    # ── India ─────────────────────────────────────────────────────────────
    insert_brackets(
        "India",
        "income",
        [
            (300000, 0.0),
            (700000, 0.05),
            (1000000, 0.10),
            (1200000, 0.15),
            (1500000, 0.20),
            (float("inf"), 0.30),
        ],
        "INR",
    )

    # ── Australia ─────────────────────────────────────────────────────────
    insert_brackets(
        "Australia",
        "income",
        [
            (18200, 0.0),
            (45000, 0.16),
            (135000, 0.30),
            (190000, 0.37),
            (float("inf"), 0.45),
        ],
        "AUD",
    )

    # ── Singapore ─────────────────────────────────────────────────────────
    insert_brackets(
        "Singapore",
        "income",
        [
            (20000, 0.0),
            (30000, 0.02),
            (40000, 0.035),
            (80000, 0.07),
            (120000, 0.115),
            (160000, 0.15),
            (200000, 0.18),
            (240000, 0.19),
            (280000, 0.195),
            (320000, 0.20),
            (float("inf"), 0.22),
        ],
        "SGD",
    )

    # ── Hong Kong ─────────────────────────────────────────────────────────
    insert_brackets(
        "Hong Kong",
        "income",
        [
            (50000, 0.02),
            (100000, 0.06),
            (150000, 0.10),
            (200000, 0.14),
            (float("inf"), 0.17),
        ],
        "HKD",
    )

    # ── Japan ─────────────────────────────────────────────────────────────
    insert_brackets(
        "Japan",
        "income",
        [
            (1950000, 0.05),
            (3300000, 0.10),
            (6950000, 0.20),
            (9000000, 0.23),
            (18000000, 0.33),
            (40000000, 0.40),
            (float("inf"), 0.45),
        ],
        "JPY",
    )

    # ── South Korea ───────────────────────────────────────────────────────
    insert_brackets(
        "South Korea",
        "income",
        [
            (14000000, 0.06),
            (50000000, 0.15),
            (88000000, 0.24),
            (150000000, 0.35),
            (300000000, 0.38),
            (500000000, 0.40),
            (1000000000, 0.42),
            (float("inf"), 0.45),
        ],
        "KRW",
    )

    # ── Israel ────────────────────────────────────────────────────────────
    insert_brackets(
        "Israel",
        "income",
        [
            (81480, 0.10),
            (116760, 0.14),
            (167880, 0.20),
            (241680, 0.31),
            (502920, 0.35),
            (647640, 0.47),
            (float("inf"), 0.50),
        ],
        "ILS",
    )

    # ── China ─────────────────────────────────────────────────────────────
    insert_brackets(
        "China",
        "income",
        [
            (36000, 0.03),
            (144000, 0.10),
            (300000, 0.20),
            (420000, 0.25),
            (660000, 0.30),
            (960000, 0.35),
            (float("inf"), 0.45),
        ],
        "CNY",
    )

    # ── Sweden ────────────────────────────────────────────────────────────
    # Sweden uses municipal + state above threshold; store as brackets
    insert_brackets(
        "Sweden",
        "income",
        [
            (598500, 0.32),
            (float("inf"), 0.52),  # 0.32 municipal + 0.20 state above threshold
        ],
        "SEK",
    )

    # ── Denmark ───────────────────────────────────────────────────────────
    # Simplified: AM-bidrag 8%, then brackets on remainder
    insert_brackets(
        "Denmark",
        "income",
        [
            (49700, 0.0),
            (588900, 0.3709),
            (float("inf"), 0.5207),
        ],
        "DKK",
    )

    # ── Norway ────────────────────────────────────────────────────────────
    insert_brackets(
        "Norway",
        "trinnskatt",
        [
            (208050, 0.0),
            (292850, 0.017),
            (670000, 0.04),
            (937900, 0.136),
            (1350000, 0.166),
            (float("inf"), 0.176),
        ],
        "NOK",
    )

    # ── Finland ───────────────────────────────────────────────────────────
    insert_brackets(
        "Finland",
        "income",
        [
            (19900, 0.0),
            (29700, 0.1264),
            (49000, 0.2132),
            (85800, 0.3012),
            (float("inf"), 0.4412),
        ],
        "EUR",
    )

    # ── Belgium ───────────────────────────────────────────────────────────
    insert_brackets(
        "Belgium",
        "income",
        [
            (15200, 0.25),
            (26830, 0.40),
            (46440, 0.45),
            (float("inf"), 0.50),
        ],
        "EUR",
    )

    # ── Austria ───────────────────────────────────────────────────────────
    insert_brackets(
        "Austria",
        "income",
        [
            (11693, 0.0),
            (19134, 0.20),
            (32075, 0.30),
            (62080, 0.40),
            (93120, 0.48),
            (1000000, 0.50),
            (float("inf"), 0.55),
        ],
        "EUR",
    )

    # ── Italy ─────────────────────────────────────────────────────────────
    insert_brackets(
        "Italy",
        "income",
        [
            (28000, 0.23),
            (50000, 0.35),
            (float("inf"), 0.43),
        ],
        "EUR",
    )

    # ── Spain ─────────────────────────────────────────────────────────────
    insert_brackets(
        "Spain",
        "income",
        [
            (12450, 0.19),
            (20200, 0.24),
            (35200, 0.30),
            (60000, 0.37),
            (300000, 0.45),
            (float("inf"), 0.47),
        ],
        "EUR",
    )

    # ── Portugal ──────────────────────────────────────────────────────────
    insert_brackets(
        "Portugal",
        "income",
        [
            (7703, 0.1325),
            (11623, 0.18),
            (16472, 0.23),
            (21321, 0.26),
            (27146, 0.3275),
            (39791, 0.37),
            (51997, 0.435),
            (81199, 0.45),
            (float("inf"), 0.48),
        ],
        "EUR",
    )

    # ── Poland ────────────────────────────────────────────────────────────
    insert_brackets(
        "Poland",
        "income",
        [
            (120000, 0.12),
            (float("inf"), 0.32),
        ],
        "PLN",
    )

    # ── Czech Republic ────────────────────────────────────────────────────
    insert_brackets(
        "Czech Republic",
        "income",
        [
            (1935552, 0.15),
            (float("inf"), 0.23),
        ],
        "CZK",
    )

    # ── Estonia ───────────────────────────────────────────────────────────
    insert_brackets(
        "Estonia",
        "income",
        [
            (7848, 0.0),
            (float("inf"), 0.20),
        ],
        "EUR",
    )

    # ── New Zealand ───────────────────────────────────────────────────────
    insert_brackets(
        "New Zealand",
        "income",
        [
            (14000, 0.105),
            (48000, 0.175),
            (70000, 0.30),
            (180000, 0.33),
            (float("inf"), 0.39),
        ],
        "NZD",
    )

    # ── Taiwan ────────────────────────────────────────────────────────────
    insert_brackets(
        "Taiwan",
        "income",
        [
            (560000, 0.05),
            (1260000, 0.12),
            (2520000, 0.20),
            (4720000, 0.30),
            (float("inf"), 0.40),
        ],
        "TWD",
    )

    # ── South Africa ──────────────────────────────────────────────────────
    insert_brackets(
        "South Africa",
        "income",
        [
            (237100, 0.18),
            (370500, 0.26),
            (512800, 0.31),
            (673000, 0.36),
            (857900, 0.39),
            (1817000, 0.41),
            (float("inf"), 0.45),
        ],
        "ZAR",
    )

    # ── Egypt ─────────────────────────────────────────────────────────────
    insert_brackets(
        "Egypt",
        "income",
        [
            (40000, 0.0),
            (55000, 0.10),
            (70000, 0.15),
            (200000, 0.20),
            (400000, 0.225),
            (float("inf"), 0.25),
        ],
        "EGP",
    )

    # ── Brazil ────────────────────────────────────────────────────────────
    insert_brackets(
        "Brazil",
        "income",
        [
            (26963.20, 0.0),
            (33919.80, 0.075),
            (45012.60, 0.15),
            (55976.16, 0.225),
            (float("inf"), 0.275),
        ],
        "BRL",
    )

    # ── Mexico ────────────────────────────────────────────────────────────
    insert_brackets(
        "Mexico",
        "income",
        [
            (8952.49, 0.0192),
            (75984.55, 0.064),
            (133536.07, 0.1088),
            (155229.80, 0.16),
            (185852.57, 0.1792),
            (374837.88, 0.2136),
            (590795.99, 0.2352),
            (1127926.84, 0.30),
            (1503902.46, 0.32),
            (4511707.37, 0.34),
            (float("inf"), 0.35),
        ],
        "MXN",
    )

    # ── Chile ─────────────────────────────────────────────────────────────
    insert_brackets(
        "Chile",
        "income",
        [
            (8775900, 0.0),
            (19502000, 0.04),
            (32503333, 0.08),
            (45504667, 0.135),
            (58506000, 0.23),
            (78008000, 0.304),
            (float("inf"), 0.35),
        ],
        "CLP",
    )

    # ── Colombia ──────────────────────────────────────────────────────────
    insert_brackets(
        "Colombia",
        "income",
        [
            (49869000, 0.0),
            (77755000, 0.19),
            (165413000, 0.28),
            (365542000, 0.33),
            (float("inf"), 0.35),
        ],
        "COP",
    )

    # ── Pakistan ──────────────────────────────────────────────────────────
    insert_brackets(
        "Pakistan",
        "income",
        [
            (600000, 0.0),
            (1200000, 0.05),
            (2200000, 0.15),
            (3200000, 0.25),
            (4100000, 0.30),
            (float("inf"), 0.35),
        ],
        "PKR",
    )

    # ── Saudi Arabia (no income tax — special handling in config) ─────────
    # ── UAE (no income tax — special handling in config) ──────────────────

    logger.info("Imported %d tax brackets", count)


# ═════════════════════════════════════════════════════════════════════════════
# TAX CONFIG (deductions, social rates, caps, flags)
# ═════════════════════════════════════════════════════════════════════════════


def _import_tax_config(cursor):
    """Import per-country tax configuration parameters."""
    cursor.execute("DELETE FROM tax_config")
    count = 0

    def insert_config(country, scope, key, value, desc=""):
        nonlocal count
        cursor.execute(
            "INSERT INTO tax_config (country, scope, config_key, config_value, description) "
            "VALUES (?, ?, ?, ?, ?)",
            (country, scope, key, value, desc),
        )
        count += 1

    # ── USA Federal ──────────────────────────────────────────────────────
    insert_config(
        "USA",
        "federal",
        "standard_deduction",
        14600,
        "Standard deduction for single filer 2024",
    )
    insert_config("USA", "federal", "ss_wage_base", 168600, "Social Security wage base")
    insert_config("USA", "federal", "ss_rate", 0.062, "Social Security rate")
    insert_config("USA", "federal", "medicare_rate", 0.0145, "Medicare rate")
    insert_config(
        "USA",
        "federal",
        "medicare_surtax_threshold",
        200000,
        "Additional Medicare surtax threshold",
    )
    insert_config(
        "USA",
        "federal",
        "medicare_surtax_rate",
        0.009,
        "Additional Medicare surtax rate",
    )

    # ── USA State deductions ─────────────────────────────────────────────
    state_deductions = {
        "CA": 5540,
        "NY": 8000,
        "NJ": 0,
        "MD": 2400,
        "DC": 14600,
        "GA": 5400,
        "MA": 0,
        "IL": 0,
        "PA": 0,
        "TX": 0,
        "WA": 0,
    }
    for state, deduction in state_deductions.items():
        insert_config(
            "USA",
            f"state_{state}",
            "standard_deduction",
            deduction,
            f"{state} standard deduction",
        )

    # ── UK ────────────────────────────────────────────────────────────────
    insert_config(
        "UK", "income", "personal_allowance_lc", 12570, "Personal allowance in GBP"
    )
    insert_config("UK", "income", "pa_taper_start_lc", 100000, "PA taper start in GBP")
    insert_config("UK", "income", "currency", 0.79, "GBP per USD (stored as rate)")

    # ── Canada ────────────────────────────────────────────────────────────
    insert_config(
        "Canada", "federal", "personal_amount_lc", 15705, "Basic personal amount CAD"
    )
    insert_config(
        "Canada",
        "provincial_ontario",
        "personal_amount_lc",
        11865,
        "Ontario personal amount CAD",
    )
    insert_config("Canada", "social", "cpp_rate", 0.0595, "CPP employee rate")
    insert_config(
        "Canada", "social", "cpp_max_lc", 3867, "Max annual CPP contribution CAD"
    )
    insert_config("Canada", "social", "ei_rate", 0.0166, "EI employee rate")
    insert_config(
        "Canada", "social", "ei_max_lc", 1049, "Max annual EI contribution CAD"
    )

    # Ontario surtax and health premium
    insert_config(
        "Canada",
        "provincial_ontario",
        "surtax_threshold1_lc",
        4991,
        "Ontario surtax threshold 1 CAD",
    )
    insert_config(
        "Canada",
        "provincial_ontario",
        "surtax_rate1",
        0.20,
        "Ontario surtax rate on excess above threshold 1",
    )
    insert_config(
        "Canada",
        "provincial_ontario",
        "surtax_threshold2_lc",
        6387,
        "Ontario surtax threshold 2 CAD",
    )
    insert_config(
        "Canada",
        "provincial_ontario",
        "surtax_rate2",
        0.36,
        "Ontario surtax rate on excess above threshold 2",
    )
    insert_config(
        "Canada",
        "provincial_ontario",
        "ohp_max_lc",
        900,
        "Ontario Health Premium max CAD",
    )

    # ── Germany ───────────────────────────────────────────────────────────
    insert_config(
        "Germany",
        "social",
        "rate",
        0.196,
        "Social contribution rate (health+pension+unemployment+care)",
    )
    insert_config(
        "Germany", "social", "cap_lc", 90600, "Social contribution cap in EUR"
    )
    insert_config(
        "Germany",
        "income",
        "soli_threshold_lc",
        18130,
        "Solidaritaetszuschlag threshold in EUR",
    )
    insert_config(
        "Germany",
        "income",
        "soli_rate",
        0.055,
        "Solidaritaetszuschlag rate on income tax",
    )

    # ── Switzerland ───────────────────────────────────────────────────────
    insert_config(
        "Switzerland",
        "cantonal",
        "effective_rate",
        0.12,
        "Zurich cantonal+municipal effective rate",
    )
    insert_config(
        "Switzerland",
        "social",
        "rate",
        0.134,
        "Social contribution rate (AHV/IV/EO+ALV+pension)",
    )
    insert_config(
        "Switzerland", "social", "cap_lc", 148200, "Social contribution cap in CHF"
    )

    # ── France ────────────────────────────────────────────────────────────
    insert_config(
        "France",
        "income",
        "professional_deduction_rate",
        0.10,
        "10% professional expense deduction",
    )
    insert_config(
        "France", "social", "rate", 0.097, "Employee social: CSG 9.2% + CRDS 0.5%"
    )

    # ── India ─────────────────────────────────────────────────────────────
    insert_config(
        "India", "income", "cess_rate", 0.04, "Health & education cess on income tax"
    )
    insert_config(
        "India",
        "social",
        "epf_rate",
        0.06,
        "EPF effective rate (~12% of basic ~50% of gross)",
    )

    # ── Australia ─────────────────────────────────────────────────────────
    insert_config("Australia", "social", "medicare_rate", 0.02, "Medicare levy rate")

    # ── Singapore ─────────────────────────────────────────────────────────
    insert_config("Singapore", "social", "cpf_rate", 0.20, "CPF employee rate")
    insert_config(
        "Singapore", "social", "cpf_cap_monthly_lc", 6800, "CPF monthly ceiling SGD"
    )

    # ── Hong Kong ─────────────────────────────────────────────────────────
    insert_config(
        "Hong Kong", "income", "personal_allowance_lc", 132000, "Personal allowance HKD"
    )
    insert_config("Hong Kong", "income", "standard_rate", 0.15, "Standard rate cap")
    insert_config("Hong Kong", "social", "mpf_rate", 0.05, "MPF employee rate")
    insert_config(
        "Hong Kong", "social", "mpf_cap_monthly_lc", 1500, "MPF monthly cap HKD"
    )

    # ── Japan ─────────────────────────────────────────────────────────────
    insert_config(
        "Japan", "income", "resident_tax_rate", 0.10, "Resident tax flat rate"
    )
    insert_config(
        "Japan",
        "income",
        "reconstruction_surtax_rate",
        0.021,
        "Reconstruction surtax on income tax",
    )
    insert_config(
        "Japan",
        "income",
        "employment_deduction_low_lc",
        550000,
        "Employment deduction for low income JPY",
    )
    insert_config(
        "Japan",
        "income",
        "employment_deduction_mid_add_lc",
        440000,
        "Employment deduction mid-range addend JPY",
    )
    insert_config(
        "Japan",
        "income",
        "employment_deduction_mid_rate",
        0.2,
        "Employment deduction mid-range rate",
    )
    insert_config(
        "Japan",
        "income",
        "employment_deduction_high_lc",
        1950000,
        "Employment deduction cap JPY",
    )
    insert_config(
        "Japan",
        "income",
        "employment_deduction_low_threshold_lc",
        1625000,
        "Low income threshold JPY",
    )
    insert_config(
        "Japan",
        "income",
        "employment_deduction_high_threshold_lc",
        8500000,
        "High income threshold JPY",
    )
    insert_config(
        "Japan",
        "social",
        "rate",
        0.145,
        "Employee social: pension 9.15% + health 5% + emp ins 0.3%",
    )
    insert_config(
        "Japan", "social", "cap_monthly_lc", 1390000, "Pension cap monthly JPY"
    )
    insert_config(
        "Japan",
        "income",
        "basic_exemption_lc",
        480000,
        "Basic exemption (kiso kojo) in JPY",
    )

    # ── South Korea ───────────────────────────────────────────────────────
    insert_config(
        "South Korea",
        "income",
        "local_tax_rate",
        0.10,
        "Local income tax rate (% of national)",
    )
    insert_config("South Korea", "social", "rate", 0.094, "Social contribution rate")
    insert_config(
        "South Korea", "social", "cap_monthly_lc", 5900000, "NPS cap monthly KRW"
    )

    # ── Israel ────────────────────────────────────────────────────────────
    insert_config("Israel", "social", "rate", 0.12, "National Insurance + Health rate")

    # ── China ─────────────────────────────────────────────────────────────
    insert_config(
        "China",
        "income",
        "standard_deduction_lc",
        60000,
        "Standard deduction CNY (5000/mo)",
    )
    insert_config("China", "social", "rate", 0.105, "Social insurance rate")
    insert_config("China", "social", "cap_lc", 360000, "Social insurance cap CNY")
    insert_config(
        "China",
        "income",
        "social_before_tax",
        1,
        "Flag: deduct social before calculating income tax",
    )

    # ── Sweden ────────────────────────────────────────────────────────────
    insert_config("Sweden", "income", "municipal_rate", 0.32, "Municipal tax rate")
    insert_config(
        "Sweden", "income", "state_threshold_lc", 598500, "State tax threshold SEK"
    )
    insert_config(
        "Sweden", "income", "state_rate", 0.20, "State tax rate above threshold"
    )
    insert_config("Sweden", "social", "pension_rate", 0.07, "Employee pension rate")
    insert_config(
        "Sweden", "social", "pension_cap_lc", 599250, "Pension contribution cap SEK"
    )

    # ── Denmark ───────────────────────────────────────────────────────────
    insert_config(
        "Denmark", "income", "am_bidrag_rate", 0.08, "Labor market contribution rate"
    )
    insert_config(
        "Denmark", "income", "personal_allowance_lc", 49700, "Personal allowance DKK"
    )
    insert_config(
        "Denmark", "income", "municipal_rate", 0.25, "Municipal + church + health rate"
    )
    insert_config(
        "Denmark", "income", "state_bottom_rate", 0.1209, "Bottom state bracket rate"
    )
    insert_config(
        "Denmark", "income", "top_threshold_lc", 588900, "Top bracket threshold DKK"
    )
    insert_config("Denmark", "income", "top_rate", 0.15, "Top bracket additional rate")
    insert_config(
        "Denmark", "income", "tax_ceiling", 0.5207, "Effective tax ceiling rate"
    )
    insert_config(
        "Denmark", "social", "atp_annual_lc", 3408, "ATP annual contribution DKK"
    )

    # ── Norway ────────────────────────────────────────────────────────────
    insert_config(
        "Norway", "income", "flat_rate", 0.22, "Flat ordinary income tax rate"
    )
    insert_config(
        "Norway", "income", "personal_allowance_lc", 109950, "Personal allowance NOK"
    )
    insert_config(
        "Norway", "social", "rate", 0.079, "Employee social contribution rate"
    )

    # ── Finland ───────────────────────────────────────────────────────────
    insert_config(
        "Finland", "income", "municipal_rate", 0.20, "Average municipal tax rate"
    )
    insert_config(
        "Finland",
        "social",
        "rate",
        0.106,
        "Social contribution rate (pension+unemployment+health)",
    )

    # ── Belgium ───────────────────────────────────────────────────────────
    insert_config(
        "Belgium", "income", "personal_allowance_lc", 10160, "Personal allowance EUR"
    )
    insert_config(
        "Belgium",
        "income",
        "municipal_surcharge_rate",
        0.07,
        "Municipal surcharge as % of income tax",
    )
    insert_config("Belgium", "social", "rate", 0.1307, "Social contribution rate")

    # ── Austria ───────────────────────────────────────────────────────────
    insert_config("Austria", "social", "rate", 0.1812, "Social contribution rate")
    insert_config("Austria", "social", "cap_lc", 78540, "Social contribution cap EUR")

    # ── Italy ─────────────────────────────────────────────────────────────
    insert_config(
        "Italy",
        "income",
        "surcharge_rate",
        0.025,
        "Regional + municipal surcharge rate",
    )
    insert_config("Italy", "social", "rate", 0.0919, "Social contribution rate")

    # ── Spain ─────────────────────────────────────────────────────────────
    insert_config(
        "Spain", "income", "personal_allowance_lc", 5550, "Personal allowance EUR"
    )
    insert_config("Spain", "social", "rate", 0.0635, "Social contribution rate")
    insert_config("Spain", "social", "cap_lc", 56844, "Social contribution cap EUR")

    # ── Portugal ──────────────────────────────────────────────────────────
    insert_config("Portugal", "social", "rate", 0.11, "Social contribution rate")

    # ── Poland ────────────────────────────────────────────────────────────
    insert_config(
        "Poland", "income", "personal_allowance_lc", 30000, "Personal allowance PLN"
    )
    insert_config("Poland", "social", "rate", 0.1371, "Social contribution rate")
    insert_config("Poland", "social", "cap_lc", 234720, "Social contribution cap PLN")
    insert_config(
        "Poland",
        "social",
        "health_rate",
        0.09,
        "Health contribution rate (on gross-social)",
    )

    # ── Czech Republic ────────────────────────────────────────────────────
    insert_config("Czech Republic", "social", "rate", 0.11, "Social + health rate")

    # ── Estonia ───────────────────────────────────────────────────────────
    insert_config("Estonia", "social", "rate", 0.036, "Unemployment + pension rate")

    # ── New Zealand ───────────────────────────────────────────────────────
    insert_config("New Zealand", "social", "acc_rate", 0.016, "ACC levy rate")

    # ── Taiwan ────────────────────────────────────────────────────────────
    insert_config(
        "Taiwan", "income", "standard_deduction_lc", 124000, "Standard deduction TWD"
    )
    insert_config("Taiwan", "social", "rate", 0.035, "NHI + Labor insurance rate")

    # ── Saudi Arabia ──────────────────────────────────────────────────────
    insert_config(
        "Saudi Arabia", "income", "zero_tax", 1, "Flag: no income tax for employees"
    )
    insert_config("Saudi Arabia", "social", "gosi_rate", 0.0975, "GOSI rate")

    # ── UAE ───────────────────────────────────────────────────────────────
    insert_config("UAE", "income", "zero_tax", 1, "Flag: no income tax")
    insert_config("UAE", "social", "rate", 0.0, "No social contributions for expats")

    # ── South Africa ──────────────────────────────────────────────────────
    insert_config(
        "South Africa", "income", "primary_rebate_lc", 17235, "Primary rebate ZAR"
    )
    insert_config("South Africa", "social", "uif_rate", 0.01, "UIF rate")
    insert_config(
        "South Africa", "social", "uif_cap_monthly_lc", 177.12, "UIF monthly cap ZAR"
    )

    # ── Egypt ─────────────────────────────────────────────────────────────
    insert_config("Egypt", "social", "rate", 0.11, "Social contribution rate")

    # ── Brazil ────────────────────────────────────────────────────────────
    insert_config("Brazil", "social", "inss_rate", 0.11, "INSS rate")
    insert_config(
        "Brazil", "social", "inss_cap_monthly_lc", 908.85, "INSS monthly cap BRL"
    )

    # ── Mexico ────────────────────────────────────────────────────────────
    insert_config("Mexico", "social", "imss_rate", 0.03, "IMSS employee rate")

    # ── Chile ─────────────────────────────────────────────────────────────
    insert_config(
        "Chile", "social", "afp_rate", 0.125, "AFP pension rate (incl commission)"
    )

    # ── Colombia ──────────────────────────────────────────────────────────
    insert_config("Colombia", "social", "rate", 0.08, "Pension + health rate")

    # ── Pakistan ──────────────────────────────────────────────────────────
    # No special config needed — simple bracket-only system

    # ── Generic fallback ─────────────────────────────────────────────────
    insert_config(
        "_generic",
        "income",
        "effective_rate",
        0.30,
        "Generic fallback effective tax rate",
    )

    logger.info("Imported %d tax config entries", count)


# ═════════════════════════════════════════════════════════════════════════════
# LIVING COSTS
# ═════════════════════════════════════════════════════════════════════════════


def _import_living_costs(cursor):
    """Import per-city living costs with frugal and comfortable tiers.

    Frugal tier: outer-area apartment, cook at home, basic social, no car, no luxuries.
    Comfortable tier: better neighbourhood, dining out 2-3x/week, gym, modest car in
    car-dependent cities, market-rate childcare, one annual vacation.

    Format: (frugal_student, frugal_single, frugal_family,
             comfortable_student, comfortable_single, comfortable_family)
    """
    cursor.execute("DELETE FROM living_costs")

    # (frugal_student, frugal_single, frugal_family,
    #  comfortable_student, comfortable_single, comfortable_family)
    city_costs = {
        # ── USA ──────────────────────────────────────────────────────────
        "Bay Area": (32.0, 52.0, 120.0, 42.0, 66.0, 150.0),
        "NYC": (30.0, 50.0, 115.0, 40.0, 64.0, 145.0),
        "Los Angeles": (26.0, 42.0, 95.0, 34.0, 54.0, 120.0),
        "San Diego": (25.0, 40.0, 90.0, 32.0, 50.0, 112.0),
        "Boston": (28.0, 46.0, 105.0, 36.0, 58.0, 132.0),
        "Seattle": (25.0, 42.0, 95.0, 33.0, 54.0, 120.0),
        "Chicago": (22.0, 36.0, 82.0, 28.0, 46.0, 104.0),
        "DC": (26.0, 44.0, 100.0, 34.0, 56.0, 126.0),
        "Baltimore": (20.0, 34.0, 78.0, 26.0, 43.0, 98.0),
        "Pittsburgh": (18.0, 32.0, 72.0, 23.0, 40.0, 90.0),
        # ── UK ───────────────────────────────────────────────────────────
        "London": (22.0, 38.0, 95.0, 30.0, 48.0, 118.0),
        "Bristol": (16.0, 28.0, 58.0, 20.0, 35.0, 72.0),
        "Manchester": (15.0, 26.0, 54.0, 19.0, 33.0, 68.0),
        "Edinburgh": (16.0, 27.0, 56.0, 20.0, 34.0, 70.0),
        "Leeds": (14.0, 24.0, 50.0, 17.0, 30.0, 62.0),
        "Sheffield": (13.0, 22.0, 46.0, 16.0, 28.0, 58.0),
        "Glasgow": (14.0, 24.0, 50.0, 17.0, 30.0, 62.0),
        # ── Canada ───────────────────────────────────────────────────────
        "Toronto": (20.0, 34.0, 72.0, 26.0, 42.0, 90.0),
        "Vancouver": (20.0, 34.0, 74.0, 26.0, 42.0, 92.0),
        "Ottawa": (16.0, 28.0, 60.0, 20.0, 35.0, 75.0),
        "Edmonton": (14.0, 26.0, 56.0, 18.0, 32.0, 70.0),
        # ── Germany ──────────────────────────────────────────────────────
        "Munich": (16.0, 30.0, 58.0, 20.0, 37.0, 72.0),
        "Berlin": (13.0, 26.0, 55.0, 17.0, 32.0, 66.0),
        "Hamburg": (14.0, 26.0, 46.0, 17.0, 32.0, 58.0),
        "Stuttgart": (14.0, 26.0, 46.0, 17.0, 32.0, 58.0),
        "Cologne": (13.0, 24.0, 44.0, 16.0, 30.0, 55.0),
        "Dresden": (11.0, 20.0, 38.0, 14.0, 25.0, 47.0),
        "Aachen": (11.0, 20.0, 38.0, 14.0, 25.0, 47.0),
        # ── Switzerland ──────────────────────────────────────────────────
        "Zurich": (26.0, 45.0, 110.0, 35.0, 58.0, 145.0),
        "Geneva": (26.0, 45.0, 110.0, 35.0, 58.0, 145.0),
        "Lausanne": (24.0, 40.0, 95.0, 31.0, 52.0, 125.0),
        # ── Netherlands ──────────────────────────────────────────────────
        "Amsterdam": (16.0, 30.0, 58.0, 20.0, 38.0, 72.0),
        "Eindhoven": (13.0, 24.0, 48.0, 16.0, 30.0, 60.0),
        "The Hague": (14.0, 26.0, 52.0, 18.0, 33.0, 65.0),
        "Maastricht": (12.0, 22.0, 44.0, 15.0, 28.0, 55.0),
        # ── France ───────────────────────────────────────────────────────
        "Paris": (18.0, 32.0, 65.0, 24.0, 42.0, 84.0),
        # ── Italy ────────────────────────────────────────────────────────
        "Milan": (15.0, 26.0, 52.0, 19.0, 33.0, 65.0),
        "Rome": (14.0, 24.0, 48.0, 18.0, 30.0, 60.0),
        # ── Spain ────────────────────────────────────────────────────────
        "Barcelona": (13.0, 22.0, 46.0, 17.0, 28.0, 58.0),
        "Madrid": (13.0, 22.0, 46.0, 17.0, 28.0, 58.0),
        # ── Scandinavia ──────────────────────────────────────────────────
        "Copenhagen": (16.0, 28.0, 56.0, 21.0, 36.0, 72.0),
        "Stockholm": (15.0, 26.0, 54.0, 20.0, 34.0, 70.0),
        "Gothenburg": (14.0, 24.0, 50.0, 18.0, 30.0, 62.0),
        "Oslo": (18.0, 30.0, 60.0, 23.0, 38.0, 78.0),
        "Helsinki": (14.0, 24.0, 50.0, 18.0, 30.0, 62.0),
        # ── Belgium ──────────────────────────────────────────────────────
        "Brussels": (13.0, 24.0, 48.0, 17.0, 30.0, 60.0),
        "Ghent": (12.0, 22.0, 44.0, 15.0, 28.0, 55.0),
        # ── Other Europe ─────────────────────────────────────────────────
        "Vienna": (14.0, 24.0, 48.0, 18.0, 30.0, 60.0),
        "Lisbon": (12.0, 20.0, 42.0, 15.0, 25.0, 52.0),
        "Prague": (10.0, 18.0, 36.0, 13.0, 23.0, 45.0),
        "Warsaw": (10.0, 18.0, 36.0, 13.0, 23.0, 45.0),
        "Krakow": (9.0, 16.0, 32.0, 11.0, 20.0, 40.0),
        "Tallinn": (10.0, 18.0, 36.0, 13.0, 23.0, 45.0),
        # ── Australia ────────────────────────────────────────────────────
        "Sydney": (20.0, 36.0, 78.0, 26.0, 46.0, 100.0),
        "Melbourne": (18.0, 32.0, 70.0, 24.0, 42.0, 90.0),
        "Brisbane": (16.0, 28.0, 62.0, 20.0, 36.0, 78.0),
        "Perth": (16.0, 28.0, 62.0, 20.0, 36.0, 78.0),
        # ── New Zealand ──────────────────────────────────────────────────
        "Auckland": (16.0, 28.0, 62.0, 20.0, 36.0, 78.0),
        # ── India ────────────────────────────────────────────────────────
        "Bangalore": (5.0, 11.0, 21.0, 7.0, 16.0, 30.0),
        "Mumbai": (6.0, 13.0, 24.0, 8.0, 18.0, 34.0),
        "Delhi": (5.0, 10.0, 20.0, 7.0, 15.0, 28.0),
        # ── Singapore / Hong Kong ────────────────────────────────────────
        "Singapore": (20.0, 38.0, 85.0, 28.0, 50.0, 108.0),
        "Hong Kong": (20.0, 36.0, 78.0, 26.0, 48.0, 100.0),
        # ── Israel ───────────────────────────────────────────────────────
        "Tel Aviv": (16.0, 28.0, 60.0, 21.0, 36.0, 76.0),
        # ── Japan ────────────────────────────────────────────────────────
        "Tokyo": (14.0, 26.0, 55.0, 18.0, 33.0, 68.0),
        # ── South Korea ──────────────────────────────────────────────────
        "Seoul": (12.0, 22.0, 48.0, 16.0, 28.0, 60.0),
        # ── China ────────────────────────────────────────────────────────
        "Beijing": (8.0, 16.0, 32.0, 10.0, 22.0, 42.0),
        "Shanghai": (9.0, 18.0, 35.0, 12.0, 24.0, 46.0),
        # ── Taiwan ───────────────────────────────────────────────────────
        "Taipei": (8.0, 16.0, 32.0, 10.0, 21.0, 42.0),
        # ── Middle East ──────────────────────────────────────────────────
        "Dubai": (20.0, 38.0, 85.0, 28.0, 50.0, 108.0),
        "Jeddah": (14.0, 24.0, 52.0, 18.0, 32.0, 66.0),
        # ── Africa ───────────────────────────────────────────────────────
        "Cairo": (4.0, 8.0, 18.0, 6.0, 12.0, 25.0),
        "Cape Town": (8.0, 14.0, 28.0, 10.0, 18.0, 36.0),
        "Johannesburg": (7.0, 13.0, 26.0, 9.0, 17.0, 34.0),
        # ── Latin America ────────────────────────────────────────────────
        "Sao Paulo": (8.0, 14.0, 30.0, 11.0, 19.0, 40.0),
        "Rio de Janeiro": (7.0, 13.0, 28.0, 10.0, 18.0, 38.0),
        "Mexico City": (7.0, 12.0, 26.0, 9.0, 16.0, 35.0),
        "Santiago": (8.0, 14.0, 30.0, 10.0, 18.0, 38.0),
        "Bogota": (6.0, 11.0, 24.0, 8.0, 15.0, 32.0),
        # ── Pakistan (baseline) ──────────────────────────────────────────
        "Pakistan": (4.0, 8.7, 15.6, 5.5, 12.0, 22.0),
    }

    for city, (
        student,
        single,
        family,
        c_student,
        c_single,
        c_family,
    ) in city_costs.items():
        cursor.execute(
            "INSERT INTO living_costs (city, student_cost_k, single_cost_k, family_cost_k, "
            "comfortable_student_cost_k, comfortable_single_cost_k, comfortable_family_cost_k) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (city, student, single, family, c_student, c_single, c_family),
        )
    logger.info(
        "Imported %d city living costs (frugal + comfortable tiers)", len(city_costs)
    )


# ═════════════════════════════════════════════════════════════════════════════
# COUNTRY DEFAULT CITIES
# ═════════════════════════════════════════════════════════════════════════════


def _import_country_default_cities(cursor):
    """Import country-to-default-city fallback mappings."""
    cursor.execute("DELETE FROM country_default_cities")

    mappings = {
        "USA": "Bay Area",
        "UK": "London",
        "Canada": "Toronto",
        "Germany": "Berlin",
        "Switzerland": "Zurich",
        "France": "Paris",
        "Netherlands": "Amsterdam",
        "Italy": "Milan",
        "Spain": "Madrid",
        "Denmark": "Copenhagen",
        "Sweden": "Stockholm",
        "Norway": "Oslo",
        "Finland": "Helsinki",
        "Belgium": "Brussels",
        "Austria": "Vienna",
        "Portugal": "Lisbon",
        "Poland": "Warsaw",
        "Czech Republic": "Prague",
        "Estonia": "Tallinn",
        "Australia": "Sydney",
        "New Zealand": "Auckland",
        "India": "Bangalore",
        "Singapore": "Singapore",
        "Hong Kong": "Hong Kong",
        "Israel": "Tel Aviv",
        "Japan": "Tokyo",
        "South Korea": "Seoul",
        "China": "Beijing",
        "Taiwan": "Taipei",
        "UAE": "Dubai",
        "Saudi Arabia": "Jeddah",
        "South Africa": "Cape Town",
        "Egypt": "Cairo",
        "Brazil": "Sao Paulo",
        "Mexico": "Mexico City",
        "Chile": "Santiago",
        "Colombia": "Bogota",
        "Pakistan": "Pakistan",
        "Lebanon": "Beirut",
        "Multi-country": "Paris",
    }

    for country, city in mappings.items():
        cursor.execute(
            "INSERT INTO country_default_cities (country, default_city) VALUES (?, ?)",
            (country, city),
        )
    logger.info("Imported %d country default city mappings", len(mappings))


# ═════════════════════════════════════════════════════════════════════════════
# MARKET MAPPINGS
# ═════════════════════════════════════════════════════════════════════════════


def _import_market_mappings(cursor):
    """Import primary_market -> work location mappings."""
    cursor.execute("DELETE FROM market_mappings")

    # (primary_market, work_country, work_city, us_state)
    mappings = [
        # USA markets
        ("USA (Bay Area)", "USA", "Bay Area", "CA"),
        ("USA (Bay Area reloc.)", "USA", "Bay Area", "CA"),
        ("USA (Bay Area/NYC)", "USA", "Bay Area", "CA"),
        ("USA (SF/NYC)", "USA", "Bay Area", "CA"),
        ("USA (LA/Bay Area)", "USA", "Los Angeles", "CA"),
        ("USA (Los Angeles)", "USA", "Los Angeles", "CA"),
        ("USA (San Diego/Bay Area)", "USA", "San Diego", "CA"),
        ("USA (NYC)", "USA", "NYC", "NY"),
        ("USA (NYC/Global)", "USA", "NYC", "NY"),
        ("USA (NYC/National)", "USA", "NYC", "NY"),
        ("USA (NYC/NJ)", "USA", "NYC", "NY"),
        ("USA (NYC/Chicago)", "USA", "NYC", "NY"),
        ("USA (NJ/NYC)", "USA", "NYC", "NJ"),
        ("USA (Boston)", "USA", "Boston", "MA"),
        ("USA (Boston/National)", "USA", "Boston", "MA"),
        ("USA (Chicago/NYC)", "USA", "Chicago", "IL"),
        ("USA (DC)", "USA", "DC", "DC"),
        ("USA (Baltimore/DC)", "USA", "DC", "MD"),
        ("USA (Pittsburgh/National)", "USA", "Pittsburgh", "PA"),
        ("USA (Seattle/National)", "USA", "Seattle", "WA"),
        ("USA (Midwest)", "USA", "Chicago", "IL"),
        ("USA (Midwest/National)", "USA", "Chicago", "IL"),
        ("USA (Northeast)", "USA", "Boston", "MA"),
        ("USA (National)", "USA", "Bay Area", "CA"),
        ("USA (National/Remote)", "USA", "Bay Area", "CA"),
        ("USA / Global", "USA", "Bay Area", "CA"),
        # UK markets
        ("London", "UK", "London", None),
        ("London (City)", "UK", "London", None),
        ("London (City) / Global", "UK", "London", None),
        ("London / Global", "UK", "London", None),
        ("London / NY / HK / Paris", "UK", "London", None),
        ("London / Paris", "UK", "London", None),
        ("Bristol / London", "UK", "London", None),
        ("Bristol / SW England", "UK", "Bristol", None),
        ("Edinburgh / London", "UK", "London", None),
        ("E Midlands / London", "UK", "London", None),
        ("Midlands / London", "UK", "London", None),
        ("W Midlands / London", "UK", "London", None),
        ("Leeds / Yorkshire", "UK", "Leeds", None),
        ("Manchester", "UK", "Manchester", None),
        ("Manchester / London", "UK", "London", None),
        ("Sheffield / Yorkshire", "UK", "Sheffield", None),
        ("Glasgow / Scotland", "UK", "Glasgow", None),
        ("SE England / London", "UK", "London", None),
        ("UK / Global", "UK", "London", None),
        # Canada markets
        ("Canada (Toronto GTA)", "Canada", "Toronto", None),
        ("Canada (Toronto reloc)", "Canada", "Toronto", None),
        ("Canada (Vancouver)", "Canada", "Vancouver", None),
        ("Canada (Ottawa)", "Canada", "Ottawa", None),
        ("Canada (Edmonton)", "Canada", "Edmonton", None),
        ("Canada (Halifax \u2192 Toronto)", "Canada", "Toronto", None),
        ("Canada / Global", "Canada", "Toronto", None),
        ("Canada / USA", "Canada", "Toronto", None),
        ("Canada / USA (Seattle)", "USA", "Seattle", "WA"),
        ("Canada / USA (reloc)", "USA", "Bay Area", "CA"),
        # Germany markets
        ("Aachen / Germany", "Germany", "Aachen", None),
        ("Berlin", "Germany", "Berlin", None),
        ("Cologne / D\u00fcsseldorf", "Germany", "Cologne", None),
        ("Dresden / Saxony", "Germany", "Dresden", None),
        ("Hamburg", "Germany", "Hamburg", None),
        ("Karlsruhe / Stuttgart", "Germany", "Stuttgart", None),
        ("Munich", "Germany", "Munich", None),
        ("Munich / Germany", "Germany", "Munich", None),
        ("Stuttgart", "Germany", "Stuttgart", None),
        ("Germany (research)", "Germany", "Berlin", None),
        # Switzerland markets
        ("Zurich", "Switzerland", "Zurich", None),
        ("Zurich / EU", "Switzerland", "Zurich", None),
        ("Zurich / London", "Switzerland", "Zurich", None),
        ("Zurich / London / Global", "Switzerland", "Zurich", None),
        ("Zurich / London / Paris", "Switzerland", "Zurich", None),
        ("Geneva / Lausanne", "Switzerland", "Geneva", None),
        ("Lausanne / Global", "Switzerland", "Lausanne", None),
        ("Lausanne / Zurich", "Switzerland", "Zurich", None),
        # Netherlands markets
        ("Amsterdam", "Netherlands", "Amsterdam", None),
        ("Eindhoven / Brainport", "Netherlands", "Eindhoven", None),
        ("Groningen \u2192 Amsterdam", "Netherlands", "Amsterdam", None),
        ("Leiden / The Hague", "Netherlands", "The Hague", None),
        ("Maastricht / Cross-border", "Netherlands", "Maastricht", None),
        ("Rotterdam / Amsterdam", "Netherlands", "Amsterdam", None),
        ("Utrecht / Amsterdam", "Netherlands", "Amsterdam", None),
        # France markets
        ("Paris / EU", "France", "Paris", None),
        ("Paris / Global (academia/intl orgs)", "France", "Paris", None),
        ("Paris / London", "France", "Paris", None),
        ("Paris / London / Singapore", "France", "Paris", None),
        # Italy markets
        ("Bologna / Milan", "Italy", "Milan", None),
        ("Milan", "Italy", "Milan", None),
        ("Milan / International", "Italy", "Milan", None),
        ("Milan / London / Zurich", "Italy", "Milan", None),
        ("Rome", "Italy", "Rome", None),
        # Spain markets
        ("Barcelona", "Spain", "Barcelona", None),
        ("Madrid", "Spain", "Madrid", None),
        ("Madrid / London", "Spain", "Madrid", None),
        # Scandinavia markets
        ("Copenhagen", "Denmark", "Copenhagen", None),
        ("Gothenburg", "Sweden", "Gothenburg", None),
        ("Helsinki", "Finland", "Helsinki", None),
        ("Lund / Stockholm", "Sweden", "Stockholm", None),
        ("Oslo / Trondheim", "Norway", "Oslo", None),
        ("Stockholm", "Sweden", "Stockholm", None),
        ("Uppsala / Stockholm", "Sweden", "Stockholm", None),
        # Belgium markets
        ("Ghent / Flanders", "Belgium", "Ghent", None),
        ("Leuven / Brussels", "Belgium", "Brussels", None),
        # Other Europe
        ("Vienna", "Austria", "Vienna", None),
        ("Lisbon", "Portugal", "Lisbon", None),
        ("Tallinn / Tartu", "Estonia", "Tallinn", None),
        ("Prague", "Czech Republic", "Prague", None),
        ("Krakow", "Poland", "Krakow", None),
        ("Warsaw", "Poland", "Warsaw", None),
        # Australia markets
        ("Adelaide / Melbourne", "Australia", "Melbourne", None),
        ("Australia / Global", "Australia", "Sydney", None),
        ("Brisbane", "Australia", "Brisbane", None),
        ("Melbourne", "Australia", "Melbourne", None),
        ("Perth", "Australia", "Perth", None),
        ("Sydney", "Australia", "Sydney", None),
        # New Zealand markets
        ("Auckland", "New Zealand", "Auckland", None),
        ("Hamilton / Auckland", "New Zealand", "Auckland", None),
        # India markets
        ("India", "India", "Bangalore", None),
        ("India / Global (academia)", "India", "Bangalore", None),
        ("India / USA", "India", "Bangalore", None),
        ("India / USA (25% migrate)", "India", "Bangalore", None),
        ("India / USA / UK", "India", "Bangalore", None),
        # Singapore / Hong Kong markets
        ("Singapore", "Singapore", "Singapore", None),
        ("Singapore / Global", "Singapore", "Singapore", None),
        ("Hong Kong", "Hong Kong", "Hong Kong", None),
        ("Hong Kong / GBA", "Hong Kong", "Hong Kong", None),
        # Israel markets
        ("Beer Sheva / TLV", "Israel", "Tel Aviv", None),
        ("Israel (Haifa / TLV)", "Israel", "Tel Aviv", None),
        ("Israel (TLV)", "Israel", "Tel Aviv", None),
        ("Jerusalem / TLV", "Israel", "Tel Aviv", None),
        ("Ramat Gan / TLV", "Israel", "Tel Aviv", None),
        ("Tel Aviv", "Israel", "Tel Aviv", None),
        # Japan / Korea / China / Taiwan
        ("Tokyo", "Japan", "Tokyo", None),
        ("Osaka / Tokyo", "Japan", "Tokyo", None),
        ("Kyoto / Osaka / Tokyo", "Japan", "Tokyo", None),
        ("Seoul", "South Korea", "Seoul", None),
        ("Seoul (relocate)", "South Korea", "Seoul", None),
        ("Korea / Global", "South Korea", "Seoul", None),
        ("Beijing", "China", "Beijing", None),
        ("Shanghai", "China", "Shanghai", None),
        ("Hangzhou / Shanghai", "China", "Shanghai", None),
        ("China", "China", "Beijing", None),
        ("Taipei / Hsinchu", "Taiwan", "Taipei", None),
        ("Taipei / Hsinchu / Global", "Taiwan", "Taipei", None),
        # Middle East / Africa
        ("Saudi Arabia (Thuwal)", "Saudi Arabia", "Jeddah", None),
        ("Gulf States (relocated)", "UAE", "Dubai", None),
        ("Egypt \u2192 Gulf States", "Egypt", "Cairo", None),
        ("Cape Town", "South Africa", "Cape Town", None),
        ("Cape Town area", "South Africa", "Cape Town", None),
        ("Johannesburg", "South Africa", "Johannesburg", None),
        ("Pan-African / Intl (PhD launch)", "South Africa", "Cape Town", None),
        # Latin America
        ("S\u00e3o Paulo", "Brazil", "Sao Paulo", None),
        ("S\u00e3o Paulo / Rio", "Brazil", "Sao Paulo", None),
        ("Rio \u2192 Intl academia / quant", "Brazil", "Rio de Janeiro", None),
        ("Mexico City", "Mexico", "Mexico City", None),
        ("Mexico (nationwide)", "Mexico", "Mexico City", None),
        ("Mexico City \u2192 USA / EU", "Mexico", "Mexico City", None),
        ("Santiago", "Chile", "Santiago", None),
        ("Bogot\u00e1", "Colombia", "Bogota", None),
    ]

    for market, country, city, state in mappings:
        cursor.execute(
            "INSERT INTO market_mappings (primary_market, work_country, work_city, us_state) VALUES (?, ?, ?, ?)",
            (market, country, city, state),
        )
    logger.info("Imported %d market mappings", len(mappings))


# ═════════════════════════════════════════════════════════════════════════════
# US REGION-TO-STATE MAPPING (for dynamic parsing)
# ═════════════════════════════════════════════════════════════════════════════


def _import_us_region_states(cursor):
    """Import US region keyword to state code mapping."""
    cursor.execute("DELETE FROM us_region_states")

    mappings = {
        "bay area": ("CA", "Bay Area"),
        "sf": ("CA", "Bay Area"),
        "san francisco": ("CA", "Bay Area"),
        "silicon valley": ("CA", "Bay Area"),
        "la": ("CA", "Los Angeles"),
        "los angeles": ("CA", "Los Angeles"),
        "san diego": ("CA", "San Diego"),
        "nyc": ("NY", "NYC"),
        "new york": ("NY", "NYC"),
        "boston": ("MA", "Boston"),
        "chicago": ("IL", "Chicago"),
        "seattle": ("WA", "Seattle"),
        "dc": ("DC", "DC"),
        "washington": ("DC", "DC"),
        "baltimore": ("MD", "Baltimore"),
        "pittsburgh": ("PA", "Pittsburgh"),
        "nj": ("NJ", "NYC"),
        "new jersey": ("NJ", "NYC"),
        "midwest": ("IL", "Chicago"),
        "northeast": ("MA", "Boston"),
        "national": ("CA", "Bay Area"),
        "remote": ("CA", "Bay Area"),
        "global": ("CA", "Bay Area"),
    }

    for keyword, (state, city) in mappings.items():
        cursor.execute(
            "INSERT INTO us_region_states (region_keyword, state_code, display_city) VALUES (?, ?, ?)",
            (keyword, state, city),
        )
    logger.info("Imported %d US region-state mappings", len(mappings))


if __name__ == "__main__":
    import_all()
