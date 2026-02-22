"""
Profile Calibration Engine for Career Decision Tree

Adjusts edge probabilities based on user profile factors.
Each factor produces a multiplier on specific edges, then child groups
are re-normalized to sum to 1.0.

Multipliers are independent and composable:
  adjusted_P = base_P * product(multipliers)
  then normalized within each parent's child group.

Only 'child' edges are calibrated (transition/fallback/enables edges
keep their independent base probabilities since they don't participate
in the sum-to-1.0 constraint).
"""

import sqlite3
from collections import defaultdict

from config import DB_PATH

# ─── Default profile (matches the hardcoded user) ───────────────────────────
DEFAULT_PROFILE = {
    "years_experience": 2.0,
    "performance_rating": "strong",
    "risk_tolerance": "moderate",
    "available_savings_usd": 5000,
    "english_level": "professional",
    "gpa": 3.5,
    "gre_score": None,
    "ielts_score": None,
    "has_publications": 0,
    "has_freelance_profile": 0,
    "has_side_projects": 0,
    "quant_aptitude": "moderate",
    "current_salary_pkr": 220000,
}

# Valid enum values for validation
VALID_PERFORMANCE = ("top", "strong", "average", "below")
VALID_RISK = ("high", "moderate", "low")
VALID_ENGLISH = ("native", "professional", "intermediate", "basic")
VALID_QUANT = ("strong", "moderate", "weak")


# ═══════════════════════════════════════════════════════════════════════════════
# CALIBRATION MULTIPLIER CONSTANTS
#
# All tunable calibration weights in one place.  A multiplier > 1.0 boosts an
# edge probability, < 1.0 suppresses it, and 1.0 means no change.
# ═══════════════════════════════════════════════════════════════════════════════

# ─── Risk tolerance (root-level branch weights) ─────────────────────────────
RISK_HIGH_RISKY_BOOST = 1.4  # high risk → risky paths (trading/startup/freelance)
RISK_HIGH_STABLE_SUPPRESS = 0.85  # high risk → stable paths suppressed
RISK_LOW_RISKY_SUPPRESS = 0.6  # low risk → risky paths suppressed
RISK_LOW_STABLE_BOOST = 1.2  # low risk → stable paths boosted
RISK_HIGH_TRADE_FULLTIME = 1.3  # high risk → more likely full-time trading
RISK_HIGH_TRADE_QUIT = 0.7  # high risk → less likely to quit trading
RISK_LOW_TRADE_FULLTIME = 0.7  # low risk → less likely full-time trading
RISK_LOW_TRADE_QUIT = 1.3  # low risk → more likely to quit trading
RISK_HIGH_STARTUP_BOOST = 1.2  # high risk → startup scale/funding boost
RISK_HIGH_STARTUP_ABANDON = 0.8  # high risk → less likely to abandon startup
RISK_LOW_STARTUP_SUPPRESS = 0.8  # low risk → startup scale/funding suppressed
RISK_LOW_STARTUP_ABANDON = 1.2  # low risk → more likely to abandon startup

# ─── Performance rating ─────────────────────────────────────────────────────
PERF_TOP_PROMOTED = 1.35  # top performer → promoted at Motive
PERF_AVG_PROMOTED = 0.65  # average performer → promoted suppressed
PERF_BELOW_PROMOTED = 0.35  # below average → promoted heavily suppressed
PERF_TOP_NOTPROMOTED = 0.70  # top → less likely stuck unpromoted
PERF_AVG_NOTPROMOTED = 1.40  # average → more likely stuck unpromoted
PERF_BELOW_NOTPROMOTED = 1.70  # below → most likely stuck unpromoted
PERF_TOP_RETRY_PROMOTED = 1.30  # top → retry promotion boost
PERF_AVG_RETRY_PROMOTED = 0.70  # average → retry suppressed
PERF_BELOW_RETRY_PROMOTED = 0.45  # below → retry heavily suppressed
PERF_TOP_RETRY_LEAVE = 0.75  # top → less likely to leave after retry
PERF_AVG_RETRY_LEAVE = 1.25  # average → more likely to leave
PERF_BELOW_RETRY_LEAVE = 1.50  # below → most likely to leave
PERF_TOP_SENIOR = 1.20  # top → staff/senior promotions boosted
PERF_AVG_SENIOR = 0.80  # average → senior suppressed
PERF_BELOW_SENIOR = 0.60  # below → senior heavily suppressed

# ─── English level ──────────────────────────────────────────────────────────
ENG_NATIVE_REMOTE = 1.25  # native → remote/freelance boost
ENG_INTERMEDIATE_REMOTE = 0.65  # intermediate → remote suppressed
ENG_BASIC_REMOTE = 0.35  # basic → remote heavily suppressed
ENG_NATIVE_LOCAL = 0.90  # native → slightly less likely to stay local
ENG_INTERMEDIATE_LOCAL = 1.15  # intermediate → local boost
ENG_BASIC_LOCAL = 1.30  # basic → strong local boost

# ─── Years of experience ────────────────────────────────────────────────────
EXP_BASELINE_LOW = 1.5  # lower bound of baseline range
EXP_BASELINE_HIGH = 2.5  # upper bound of baseline range
EXP_5PLUS_PROMOTED = 1.35  # 5+ yrs → promotion boost
EXP_3PLUS_PROMOTED = 1.15  # 3+ yrs → mild promotion boost
EXP_1MINUS_PROMOTED = 0.65  # <=1 yr → promotion suppressed
EXP_5PLUS_REMOTE = 1.30  # 5+ yrs → remote job boost
EXP_3PLUS_REMOTE = 1.10  # 3+ yrs → mild remote boost
EXP_1MINUS_REMOTE = 0.70  # <=1 yr → remote suppressed
EXP_5PLUS_STAGNATE = 0.70  # 5+ yrs → less likely to stagnate
EXP_3PLUS_STAGNATE = 0.85  # 3+ yrs → slightly less stagnation
EXP_1MINUS_STAGNATE = 1.30  # <=1 yr → more likely to stagnate

# ─── Available savings ($USD) ───────────────────────────────────────────────
SAVINGS_20K_TRADING = 1.30  # $20k+ → trading entry boost
SAVINGS_10K_TRADING = 1.15  # $10k+ → mild trading boost
SAVINGS_2K_TRADING = 0.60  # <=2k → trading entry suppressed
SAVINGS_1K_TRADING = 0.30  # <=1k → trading heavily suppressed
SAVINGS_15K_STARTUP = 1.25  # $15k+ → startup entry boost
SAVINGS_10K_STARTUP = 1.10  # $10k+ → mild startup boost
SAVINGS_2K_STARTUP = 0.65  # <=2k → startup entry suppressed
SAVINGS_20K_STOCKS = 1.30  # $20k+ → stocks/options boost
SAVINGS_3K_STOCKS = 0.60  # <=3k → stocks/options suppressed
SAVINGS_1K_CRYPTO = 0.70  # <=1k → crypto suppressed
SAVINGS_10K_CRYPTO = 1.10  # $10k+ → crypto boost
SAVINGS_20K_PROFITABLE = 1.20  # $20k+ → trading profitability boost
SAVINGS_2K_PROFITABLE = 0.75  # <=2k → profitability suppressed

# ─── Quantitative aptitude ──────────────────────────────────────────────────
QUANT_STRONG_ALGO = 1.40  # strong quant → algo/quant trading boost
QUANT_WEAK_ALGO = 0.55  # weak quant → algo trading suppressed
QUANT_STRONG_PROFITABLE = 1.20  # strong → general trading profit boost
QUANT_WEAK_PROFITABLE = 0.80  # weak → trading profit suppressed
QUANT_STRONG_LOSS = 0.75  # strong → less likely trading losses
QUANT_WEAK_LOSS = 1.35  # weak → more likely trading losses

# ─── Side projects ──────────────────────────────────────────────────────────
PROJECTS_STARTUP_TRACTION = 1.30  # has projects → startup traction/funding boost
PROJECTS_STARTUP_FAILED = 0.75  # has projects → less likely startup failure
PROJECTS_REMOTE_BOOST = 1.15  # has projects → remote job portfolio boost
PROJECTS_STARTUP_ROOT = 1.20  # has projects → root→startup boost

# ─── Freelance profile ─────────────────────────────────────────────────────
FREELANCE_ROOT = 1.35  # has profile → root→freelance boost
FREELANCE_SUCCESS = 1.40  # has profile → freelance premium/fulltime boost
FREELANCE_SIDE = 1.15  # has profile → side-freelance boost
FREELANCE_DRIED = 0.65  # has profile → less likely clients dry up
FREELANCE_PLATFORM = 1.20  # has profile → platform freelancing boost

# ─── Publications ───────────────────────────────────────────────────────────
PUBS_CAREER = 1.15  # has pubs → career advancement boost
PUBS_REMOTE = 1.20  # has pubs → remote ML job boost
PUBS_STARTUP_AI = 1.15  # has pubs → AI SaaS startup boost

# ─── GPA ────────────────────────────────────────────────────────────────────
GPA_BASELINE_LOW = 3.3  # lower bound of baseline range
GPA_BASELINE_HIGH = 3.7  # upper bound of baseline range
GPA_HIGH_PROMOTED = 1.10  # high GPA → slight promotion boost
GPA_LOW_PROMOTED = 0.90  # low GPA → slight promotion suppress


def get_profile(conn=None):
    """Load user profile from database, returns dict."""
    close_conn = False
    if conn is None:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        close_conn = True

    cursor = conn.cursor()
    cursor.execute("SELECT * FROM user_profile WHERE id = 1")
    row = cursor.fetchone()

    if close_conn:
        conn.close()

    if row:
        profile = dict(row)
        profile.pop("id", None)
        return profile

    return dict(DEFAULT_PROFILE)


def save_profile(profile_data, conn=None):
    """
    Save user profile to database.
    Validates fields and merges with defaults for missing fields.
    Returns the saved profile dict.
    """
    close_conn = False
    if conn is None:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        close_conn = True

    # Merge with defaults
    merged = dict(DEFAULT_PROFILE)
    for key, val in profile_data.items():
        if key in merged and val is not None:
            merged[key] = val

    # Validate enums
    if merged["performance_rating"] not in VALID_PERFORMANCE:
        raise ValueError(
            f"performance_rating must be one of {VALID_PERFORMANCE}, "
            f"got '{merged['performance_rating']}'"
        )
    if merged["risk_tolerance"] not in VALID_RISK:
        raise ValueError(
            f"risk_tolerance must be one of {VALID_RISK}, "
            f"got '{merged['risk_tolerance']}'"
        )
    if merged["english_level"] not in VALID_ENGLISH:
        raise ValueError(
            f"english_level must be one of {VALID_ENGLISH}, "
            f"got '{merged['english_level']}'"
        )
    if merged["quant_aptitude"] not in VALID_QUANT:
        raise ValueError(
            f"quant_aptitude must be one of {VALID_QUANT}, "
            f"got '{merged['quant_aptitude']}'"
        )

    # Validate numeric ranges
    if merged["years_experience"] < 0:
        raise ValueError("years_experience must be >= 0")
    if merged["available_savings_usd"] < 0:
        raise ValueError("available_savings_usd must be >= 0")
    if merged["gpa"] is not None and not (0 <= merged["gpa"] <= 4.0):
        raise ValueError("gpa must be between 0 and 4.0")
    if merged["gre_score"] is not None and not (260 <= merged["gre_score"] <= 340):
        raise ValueError("gre_score must be between 260 and 340")
    if merged["ielts_score"] is not None and not (0 <= merged["ielts_score"] <= 9.0):
        raise ValueError("ielts_score must be between 0 and 9.0")

    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT OR REPLACE INTO user_profile (
            id, years_experience, performance_rating, risk_tolerance,
            available_savings_usd, english_level, gpa, gre_score,
            ielts_score, has_publications, has_freelance_profile,
            has_side_projects, quant_aptitude, current_salary_pkr
        ) VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            merged["years_experience"],
            merged["performance_rating"],
            merged["risk_tolerance"],
            merged["available_savings_usd"],
            merged["english_level"],
            merged["gpa"],
            merged["gre_score"],
            merged["ielts_score"],
            int(merged["has_publications"]),
            int(merged["has_freelance_profile"]),
            int(merged["has_side_projects"]),
            merged["quant_aptitude"],
            merged["current_salary_pkr"],
        ),
    )
    conn.commit()

    if close_conn:
        conn.close()

    return merged


# ═══════════════════════════════════════════════════════════════════════════════
# MULTIPLIER RULES
#
# Each rule is a function: (profile, source_id, target_id) -> multiplier (float)
# Multiplier > 1.0 = boost this edge, < 1.0 = suppress, 1.0 = no change.
# All applicable rules are multiplied together for each edge.
# After all multipliers, child groups are re-normalized to sum to 1.0.
# ═══════════════════════════════════════════════════════════════════════════════


def _risk_tolerance_multiplier(profile, source_id, target_id):
    """
    Risk tolerance shifts root-level branch weights.
    High risk → boost trading/startup, suppress stable career paths.
    Low risk → boost career/stay paths, suppress trading/startup.
    """
    risk = profile["risk_tolerance"]
    if risk == "moderate":
        return 1.0

    # Root → trading/startup/freelance
    risky_targets = {"p1_trading", "p1_startup", "p1_freelance"}
    # Root → stable career choices
    stable_targets = {"p1_promoted", "p1_notpromoted_stay", "p1_switch_local"}

    if source_id == "root":
        if risk == "high":
            if target_id in risky_targets:
                return RISK_HIGH_RISKY_BOOST
            if target_id in stable_targets:
                return RISK_HIGH_STABLE_SUPPRESS
        elif risk == "low":
            if target_id in risky_targets:
                return RISK_LOW_RISKY_SUPPRESS
            if target_id in stable_targets:
                return RISK_LOW_STABLE_BOOST

    # Within trading path: high risk → more likely to go full-time
    if risk == "high":
        if target_id == "p4_trade_fulltime":
            return RISK_HIGH_TRADE_FULLTIME
        if target_id == "p4_trade_quit":
            return RISK_HIGH_TRADE_QUIT
    elif risk == "low":
        if target_id == "p4_trade_fulltime":
            return RISK_LOW_TRADE_FULLTIME
        if target_id == "p4_trade_quit":
            return RISK_LOW_TRADE_QUIT

    # Within startup path: high risk → more likely to scale/fund, less abandon
    if risk == "high":
        if target_id in ("p4_startup_scale", "p3_startup_funded"):
            return RISK_HIGH_STARTUP_BOOST
        if target_id == "p4_startup_abandoned":
            return RISK_HIGH_STARTUP_ABANDON
    elif risk == "low":
        if target_id in ("p4_startup_scale", "p3_startup_funded"):
            return RISK_LOW_STARTUP_SUPPRESS
        if target_id == "p4_startup_abandoned":
            return RISK_LOW_STARTUP_ABANDON

    return 1.0


def _performance_multiplier(profile, source_id, target_id):
    """
    Performance rating affects promotion probability at Motive
    and career advancement edges.
    """
    perf = profile["performance_rating"]
    if perf == "strong":
        return 1.0  # baseline

    # Root → promoted at Motive
    if source_id == "root" and target_id == "p1_promoted":
        if perf == "top":
            return PERF_TOP_PROMOTED
        elif perf == "average":
            return PERF_AVG_PROMOTED
        elif perf == "below":
            return PERF_BELOW_PROMOTED

    # Root → not promoted (inverse)
    if source_id == "root" and target_id == "p1_notpromoted_stay":
        if perf == "top":
            return PERF_TOP_NOTPROMOTED
        elif perf == "average":
            return PERF_AVG_NOTPROMOTED
        elif perf == "below":
            return PERF_BELOW_NOTPROMOTED

    # Career advancement: retry promotion
    if target_id == "p3_retry_promoted":
        if perf == "top":
            return PERF_TOP_RETRY_PROMOTED
        elif perf == "average":
            return PERF_AVG_RETRY_PROMOTED
        elif perf == "below":
            return PERF_BELOW_RETRY_PROMOTED

    if target_id == "p3_retry_failed_leave":
        if perf == "top":
            return PERF_TOP_RETRY_LEAVE
        elif perf == "average":
            return PERF_AVG_RETRY_LEAVE
        elif perf == "below":
            return PERF_BELOW_RETRY_LEAVE

    # Staff/senior promotions
    if target_id in (
        "p3_l5_achieved",
        "p3_local_senior_rise",
        "p4_motive_staff",
        "p4_local_staff",
    ):
        if perf == "top":
            return PERF_TOP_SENIOR
        elif perf == "average":
            return PERF_AVG_SENIOR
        elif perf == "below":
            return PERF_BELOW_SENIOR

    return 1.0


def _english_multiplier(profile, source_id, target_id):
    """
    English level affects remote job probability and freelance success.
    'professional' is baseline (1.0).
    """
    eng = profile["english_level"]
    if eng == "professional":
        return 1.0

    # Remote USD job targets
    remote_targets = {
        "p2_l4_remoteUSD",
        "p2_np_remote",
        "p2_local_remote",
        "p3_remote_senior",
        "p3_local_switch_remote",
        "p3_local_pivot_remote",
        "p3_stagnate_remote",
        "p4_remote_staff",
        "p4_remote_stable_senior",
        "p4_l5_goremote",
        "p4_l4stall_remote",
        "p4_local_sr_remote",
        "p4_remote_sr_direct",
    }

    # Freelance targets (communication-heavy)
    freelance_targets = {
        "p3_freelance_fulltime",
        "p4_freelance_premium",
        "p4_freelance_stable",
    }

    if target_id in remote_targets or target_id in freelance_targets:
        if eng == "native":
            return ENG_NATIVE_REMOTE
        elif eng == "intermediate":
            return ENG_INTERMEDIATE_REMOTE
        elif eng == "basic":
            return ENG_BASIC_REMOTE

    # Local/stay targets get inverse boost when English is weak
    local_targets = {
        "p2_l4_switchlocal",
        "p2_l4_staymotive",
        "p3_l5_stalled_motive",
        "p4_l4stall_local_sr",
    }
    if target_id in local_targets:
        if eng == "native":
            return ENG_NATIVE_LOCAL
        elif eng == "intermediate":
            return ENG_INTERMEDIATE_LOCAL
        elif eng == "basic":
            return ENG_BASIC_LOCAL

    return 1.0


def _experience_multiplier(profile, source_id, target_id):
    """
    Years of experience affects promotion timelines and remote
    job competitiveness. Baseline is 2.0 years.
    """
    yoe = profile["years_experience"]
    if EXP_BASELINE_LOW <= yoe <= EXP_BASELINE_HIGH:
        return 1.0  # baseline range

    # More experience → higher promotion probability
    if target_id in ("p1_promoted", "p3_retry_promoted", "p2_local_promoted"):
        if yoe >= 5:
            return EXP_5PLUS_PROMOTED
        elif yoe >= 3:
            return EXP_3PLUS_PROMOTED
        elif yoe <= 1:
            return EXP_1MINUS_PROMOTED

    # More experience → better remote job odds
    if target_id in (
        "p2_l4_remoteUSD",
        "p2_np_remote",
        "p3_remote_senior",
        "p4_remote_staff",
    ):
        if yoe >= 5:
            return EXP_5PLUS_REMOTE
        elif yoe >= 3:
            return EXP_3PLUS_REMOTE
        elif yoe <= 1:
            return EXP_1MINUS_REMOTE

    # Less experience → more likely to stagnate
    if target_id in (
        "p2_local_stagnate",
        "p3_teamswitch_stuck",
        "p3_l5_stalled_motive",
    ):
        if yoe >= 5:
            return EXP_5PLUS_STAGNATE
        elif yoe >= 3:
            return EXP_3PLUS_STAGNATE
        elif yoe <= 1:
            return EXP_1MINUS_STAGNATE

    return 1.0


def _savings_multiplier(profile, source_id, target_id):
    """
    Available savings affects feasibility of capital-intensive paths.
    Baseline is $5,000 USD.
    """
    savings = profile["available_savings_usd"]

    # Trading entry (needs capital)
    if source_id == "root" and target_id == "p1_trading":
        if savings >= 20000:
            return SAVINGS_20K_TRADING
        elif savings >= 10000:
            return SAVINGS_10K_TRADING
        elif savings <= 2000:
            return SAVINGS_2K_TRADING
        elif savings <= 1000:
            return SAVINGS_1K_TRADING

    # Startup entry
    if source_id == "root" and target_id == "p1_startup":
        if savings >= 15000:
            return SAVINGS_15K_STARTUP
        elif savings >= 10000:
            return SAVINGS_10K_STARTUP
        elif savings <= 2000:
            return SAVINGS_2K_STARTUP

    # Trading: stocks/options need more capital than crypto
    if source_id == "p1_trading" and target_id == "p2_trade_stocks":
        if savings >= 20000:
            return SAVINGS_20K_STOCKS
        elif savings <= 3000:
            return SAVINGS_3K_STOCKS

    if source_id == "p1_trading" and target_id == "p2_trade_crypto":
        if savings <= 1000:
            return SAVINGS_1K_CRYPTO
        elif savings >= 10000:
            return SAVINGS_10K_CRYPTO

    # Trading profitability scales with capital
    if target_id == "p3_trade_profitable":
        if savings >= 20000:
            return SAVINGS_20K_PROFITABLE
        elif savings <= 2000:
            return SAVINGS_2K_PROFITABLE

    return 1.0


def _quant_aptitude_multiplier(profile, source_id, target_id):
    """
    Quantitative aptitude affects trading path success,
    especially algo/quant trading.
    """
    quant = profile["quant_aptitude"]
    if quant == "moderate":
        return 1.0

    # Algo trading path
    if target_id in ("p2_trade_algo", "p3_trade_algo_edge", "p4_trade_quant_fund"):
        if quant == "strong":
            return QUANT_STRONG_ALGO
        elif quant == "weak":
            return QUANT_WEAK_ALGO

    # General trading profitability
    if target_id == "p3_trade_profitable":
        if quant == "strong":
            return QUANT_STRONG_PROFITABLE
        elif quant == "weak":
            return QUANT_WEAK_PROFITABLE

    # Trading losses
    if target_id == "p3_trade_loss":
        if quant == "strong":
            return QUANT_STRONG_LOSS
        elif quant == "weak":
            return QUANT_WEAK_LOSS

    return 1.0


def _side_projects_multiplier(profile, source_id, target_id):
    """
    Existing side projects boost startup success probability
    and strengthen portfolio for remote/freelance.
    """
    has_projects = bool(profile["has_side_projects"])
    if not has_projects:
        return 1.0

    # Startup traction and funding
    if target_id in ("p3_startup_traction", "p3_startup_funded"):
        return PROJECTS_STARTUP_TRACTION
    if target_id == "p3_startup_failed":
        return PROJECTS_STARTUP_FAILED

    # Remote job applications (portfolio)
    if target_id in ("p2_l4_remoteUSD", "p2_np_remote"):
        return PROJECTS_REMOTE_BOOST

    # Root → startup becomes more likely
    if source_id == "root" and target_id == "p1_startup":
        return PROJECTS_STARTUP_ROOT

    return 1.0


def _freelance_profile_multiplier(profile, source_id, target_id):
    """
    Existing freelance profile/reviews dramatically boost
    freelance path success.
    """
    has_profile = bool(profile["has_freelance_profile"])
    if not has_profile:
        return 1.0

    # Root → freelance more likely
    if source_id == "root" and target_id == "p1_freelance":
        return FREELANCE_ROOT

    # Freelance success paths
    if target_id in ("p3_freelance_fulltime", "p4_freelance_premium"):
        return FREELANCE_SUCCESS
    if target_id == "p3_freelance_side":
        return FREELANCE_SIDE
    if target_id == "p3_freelance_dried":
        return FREELANCE_DRIED

    # Platform-based freelancing (existing reviews help)
    if target_id == "p2_freelance_platform":
        return FREELANCE_PLATFORM

    return 1.0


def _publications_multiplier(profile, source_id, target_id):
    """
    Research publications boost masters admission and
    career advancement in AI/ML roles.
    """
    has_pubs = bool(profile["has_publications"])
    if not has_pubs:
        return 1.0

    # Career advancement (research background valued)
    if target_id in ("p1_promoted", "p3_l5_achieved", "p4_motive_staff"):
        return PUBS_CAREER

    # Remote job competitiveness (ML research is valued)
    if target_id in ("p2_l4_remoteUSD", "p3_remote_senior", "p4_remote_staff"):
        return PUBS_REMOTE

    # Startup AI SaaS (research depth = better product)
    if target_id == "p2_startup_ai_saas":
        return PUBS_STARTUP_AI

    return 1.0


def _gpa_multiplier(profile, source_id, target_id):
    """
    GPA affects masters admission probability.
    Masters nodes are dynamic (not in career_nodes), but this
    multiplier is available for future masters edge calibration.
    Also slightly affects career prestige perceptions.
    """
    gpa = profile.get("gpa")
    if gpa is None or GPA_BASELINE_LOW <= gpa <= GPA_BASELINE_HIGH:
        return 1.0  # baseline range

    # Higher GPA → better promotion perception
    if target_id == "p1_promoted":
        if gpa >= 3.8:
            return GPA_HIGH_PROMOTED
        elif gpa <= 2.5:
            return GPA_LOW_PROMOTED

    return 1.0


# ─── Multiplier registry ────────────────────────────────────────────────────
# All multiplier functions are applied to each edge.
MULTIPLIER_RULES = [
    _risk_tolerance_multiplier,
    _performance_multiplier,
    _english_multiplier,
    _experience_multiplier,
    _savings_multiplier,
    _quant_aptitude_multiplier,
    _side_projects_multiplier,
    _freelance_profile_multiplier,
    _publications_multiplier,
    _gpa_multiplier,
]


def calibrate_edges(profile=None, conn=None):
    """
    Load all edges from database, apply profile-based multipliers,
    re-normalize child groups to sum to 1.0, and return calibrated edges.

    Args:
        profile: dict of profile values, or None to load from DB.
        conn: optional SQLite connection.

    Returns:
        list of edge dicts with 'calibrated_probability' added.
        Each edge dict has: id, source_id, target_id, probability (base),
        calibrated_probability, link_type, note, multiplier.
    """
    close_conn = False
    if conn is None:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        close_conn = True

    if profile is None:
        profile = get_profile(conn)

    # Load all edges
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, source_id, target_id, probability, link_type, note FROM edges"
    )
    rows = cursor.fetchall()
    edges = [dict(row) for row in rows]

    if close_conn:
        conn.close()

    # Apply multipliers to each edge
    for edge in edges:
        if edge["link_type"] != "child":
            # Non-child edges keep base probability (no normalization needed)
            edge["calibrated_probability"] = edge["probability"]
            edge["multiplier"] = 1.0
            continue

        combined_multiplier = 1.0
        for rule_fn in MULTIPLIER_RULES:
            m = rule_fn(profile, edge["source_id"], edge["target_id"])
            combined_multiplier *= m

        edge["multiplier"] = round(combined_multiplier, 4)
        edge["raw_adjusted"] = edge["probability"] * combined_multiplier

    # Re-normalize child groups to sum to 1.0
    # Group child edges by source_id
    child_groups = defaultdict(list)
    for edge in edges:
        if edge["link_type"] == "child":
            child_groups[edge["source_id"]].append(edge)

    for source_id, group in child_groups.items():
        total_raw = sum(e["raw_adjusted"] for e in group)
        if total_raw > 0:
            for e in group:
                e["calibrated_probability"] = round(e["raw_adjusted"] / total_raw, 4)
        else:
            # Fallback: equal distribution
            n = len(group)
            for e in group:
                e["calibrated_probability"] = round(1.0 / n, 4)

    # Clean up intermediate field
    for edge in edges:
        edge.pop("raw_adjusted", None)

    return edges


def get_calibrated_edge_map(profile=None, conn=None):
    """
    Convenience function: returns calibrated edges as a nested dict
    edgeMap[source_id][target_id] = calibrated_probability.
    Useful for net worth calculations and frontend consumption.
    """
    edges = calibrate_edges(profile=profile, conn=conn)
    edge_map = defaultdict(dict)
    for e in edges:
        edge_map[e["source_id"]][e["target_id"]] = e["calibrated_probability"]
    return dict(edge_map)


def get_calibration_summary(profile=None, conn=None):
    """
    Returns a summary showing which edges were most affected by calibration.
    Useful for debugging and transparency.
    """
    edges = calibrate_edges(profile=profile, conn=conn)

    changed = []
    for e in edges:
        if e["link_type"] != "child":
            continue
        base = e["probability"]
        cal = e["calibrated_probability"]
        if abs(base - cal) > 0.005:  # only report meaningful changes
            changed.append(
                {
                    "source_id": e["source_id"],
                    "target_id": e["target_id"],
                    "base_probability": base,
                    "calibrated_probability": cal,
                    "change": round(cal - base, 4),
                    "change_pct": round((cal - base) / base * 100, 1)
                    if base > 0
                    else 0,
                    "multiplier": e["multiplier"],
                }
            )

    # Sort by absolute change descending
    changed.sort(key=lambda x: abs(x["change"]), reverse=True)

    return {
        "total_edges": len(edges),
        "child_edges": len([e for e in edges if e["link_type"] == "child"]),
        "edges_changed": len(changed),
        "changes": changed,
    }
