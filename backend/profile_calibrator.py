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
from pathlib import Path

try:
    import tomllib  # Python 3.11+
except ImportError:
    import tomli as tomllib  # fallback for Python 3.10

from config import DB_PATH

# ─── Load calibration weights from TOML ─────────────────────────────────────
_WEIGHTS_PATH = Path(__file__).parent / "calibration_weights.toml"
with open(_WEIGHTS_PATH, "rb") as f:
    _W = tomllib.load(f)

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

    w = _W["risk_tolerance"]

    # Root → trading/startup/freelance
    risky_targets = {"p1_trading", "p1_startup", "p1_freelance"}
    # Root → stable career choices
    stable_targets = {"p1_promoted", "p1_notpromoted_stay", "p1_switch_local"}

    if source_id == "root":
        if risk == "high":
            if target_id in risky_targets:
                return w["high_risky_boost"]
            if target_id in stable_targets:
                return w["high_stable_suppress"]
        elif risk == "low":
            if target_id in risky_targets:
                return w["low_risky_suppress"]
            if target_id in stable_targets:
                return w["low_stable_boost"]

    # Within trading path: high risk → more likely to go full-time
    if risk == "high":
        if target_id == "p4_trade_fulltime":
            return w["high_trade_fulltime"]
        if target_id == "p4_trade_quit":
            return w["high_trade_quit"]
    elif risk == "low":
        if target_id == "p4_trade_fulltime":
            return w["low_trade_fulltime"]
        if target_id == "p4_trade_quit":
            return w["low_trade_quit"]

    # Within startup path: high risk → more likely to scale/fund, less abandon
    if risk == "high":
        if target_id in ("p4_startup_scale", "p3_startup_funded"):
            return w["high_startup_boost"]
        if target_id == "p4_startup_abandoned":
            return w["high_startup_abandon"]
    elif risk == "low":
        if target_id in ("p4_startup_scale", "p3_startup_funded"):
            return w["low_startup_suppress"]
        if target_id == "p4_startup_abandoned":
            return w["low_startup_abandon"]

    return 1.0


def _performance_multiplier(profile, source_id, target_id):
    """
    Performance rating affects promotion probability at Motive
    and career advancement edges.
    """
    perf = profile["performance_rating"]
    if perf == "strong":
        return 1.0  # baseline

    w = _W["performance"]

    # Root → promoted at Motive
    if source_id == "root" and target_id == "p1_promoted":
        if perf == "top":
            return w["top_promoted"]
        elif perf == "average":
            return w["avg_promoted"]
        elif perf == "below":
            return w["below_promoted"]

    # Root → not promoted (inverse)
    if source_id == "root" and target_id == "p1_notpromoted_stay":
        if perf == "top":
            return w["top_notpromoted"]
        elif perf == "average":
            return w["avg_notpromoted"]
        elif perf == "below":
            return w["below_notpromoted"]

    # Career advancement: retry promotion
    if target_id == "p3_retry_promoted":
        if perf == "top":
            return w["top_retry_promoted"]
        elif perf == "average":
            return w["avg_retry_promoted"]
        elif perf == "below":
            return w["below_retry_promoted"]

    if target_id == "p3_retry_failed_leave":
        if perf == "top":
            return w["top_retry_leave"]
        elif perf == "average":
            return w["avg_retry_leave"]
        elif perf == "below":
            return w["below_retry_leave"]

    # Staff/senior promotions
    if target_id in (
        "p3_l5_achieved",
        "p3_local_senior_rise",
        "p4_motive_staff",
        "p4_local_staff",
    ):
        if perf == "top":
            return w["top_senior"]
        elif perf == "average":
            return w["avg_senior"]
        elif perf == "below":
            return w["below_senior"]

    return 1.0


def _english_multiplier(profile, source_id, target_id):
    """
    English level affects remote job probability and freelance success.
    'professional' is baseline (1.0).
    """
    eng = profile["english_level"]
    if eng == "professional":
        return 1.0

    w = _W["english"]

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
            return w["native_remote"]
        elif eng == "intermediate":
            return w["intermediate_remote"]
        elif eng == "basic":
            return w["basic_remote"]

    # Local/stay targets get inverse boost when English is weak
    local_targets = {
        "p2_l4_switchlocal",
        "p2_l4_staymotive",
        "p3_l5_stalled_motive",
        "p4_l4stall_local_sr",
    }
    if target_id in local_targets:
        if eng == "native":
            return w["native_local"]
        elif eng == "intermediate":
            return w["intermediate_local"]
        elif eng == "basic":
            return w["basic_local"]

    return 1.0


def _experience_multiplier(profile, source_id, target_id):
    """
    Years of experience affects promotion timelines and remote
    job competitiveness. Baseline is 2.0 years.
    """
    yoe = profile["years_experience"]
    w = _W["experience"]

    if w["baseline_low"] <= yoe <= w["baseline_high"]:
        return 1.0  # baseline range

    # More experience → higher promotion probability
    if target_id in ("p1_promoted", "p3_retry_promoted", "p2_local_promoted"):
        if yoe >= 5:
            return w["five_plus_promoted"]
        elif yoe >= 3:
            return w["three_plus_promoted"]
        elif yoe <= 1:
            return w["one_minus_promoted"]

    # More experience → better remote job odds
    if target_id in (
        "p2_l4_remoteUSD",
        "p2_np_remote",
        "p3_remote_senior",
        "p4_remote_staff",
    ):
        if yoe >= 5:
            return w["five_plus_remote"]
        elif yoe >= 3:
            return w["three_plus_remote"]
        elif yoe <= 1:
            return w["one_minus_remote"]

    # Less experience → more likely to stagnate
    if target_id in (
        "p2_local_stagnate",
        "p3_teamswitch_stuck",
        "p3_l5_stalled_motive",
    ):
        if yoe >= 5:
            return w["five_plus_stagnate"]
        elif yoe >= 3:
            return w["three_plus_stagnate"]
        elif yoe <= 1:
            return w["one_minus_stagnate"]

    return 1.0


def _savings_multiplier(profile, source_id, target_id):
    """
    Available savings affects feasibility of capital-intensive paths.
    Baseline is $5,000 USD.
    """
    savings = profile["available_savings_usd"]
    w = _W["savings"]

    # Trading entry (needs capital)
    if source_id == "root" and target_id == "p1_trading":
        if savings >= 20000:
            return w["twenty_k_trading"]
        elif savings >= 10000:
            return w["ten_k_trading"]
        elif savings <= 2000:
            return w["two_k_trading"]
        elif savings <= 1000:
            return w["one_k_trading"]

    # Startup entry
    if source_id == "root" and target_id == "p1_startup":
        if savings >= 15000:
            return w["fifteen_k_startup"]
        elif savings >= 10000:
            return w["ten_k_startup"]
        elif savings <= 2000:
            return w["two_k_startup"]

    # Trading: stocks/options need more capital than crypto
    if source_id == "p1_trading" and target_id == "p2_trade_stocks":
        if savings >= 20000:
            return w["twenty_k_stocks"]
        elif savings <= 3000:
            return w["three_k_stocks"]

    if source_id == "p1_trading" and target_id == "p2_trade_crypto":
        if savings <= 1000:
            return w["one_k_crypto"]
        elif savings >= 10000:
            return w["ten_k_crypto"]

    # Trading profitability scales with capital
    if target_id == "p3_trade_profitable":
        if savings >= 20000:
            return w["twenty_k_profitable"]
        elif savings <= 2000:
            return w["two_k_profitable"]

    return 1.0


def _quant_aptitude_multiplier(profile, source_id, target_id):
    """
    Quantitative aptitude affects trading path success,
    especially algo/quant trading.
    """
    quant = profile["quant_aptitude"]
    if quant == "moderate":
        return 1.0

    w = _W["quant_aptitude"]

    # Algo trading path
    if target_id in ("p2_trade_algo", "p3_trade_algo_edge", "p4_trade_quant_fund"):
        if quant == "strong":
            return w["strong_algo"]
        elif quant == "weak":
            return w["weak_algo"]

    # General trading profitability
    if target_id == "p3_trade_profitable":
        if quant == "strong":
            return w["strong_profitable"]
        elif quant == "weak":
            return w["weak_profitable"]

    # Trading losses
    if target_id == "p3_trade_loss":
        if quant == "strong":
            return w["strong_loss"]
        elif quant == "weak":
            return w["weak_loss"]

    return 1.0


def _side_projects_multiplier(profile, source_id, target_id):
    """
    Existing side projects boost startup success probability
    and strengthen portfolio for remote/freelance.
    """
    has_projects = bool(profile["has_side_projects"])
    if not has_projects:
        return 1.0

    w = _W["side_projects"]

    # Startup traction and funding
    if target_id in ("p3_startup_traction", "p3_startup_funded"):
        return w["startup_traction"]
    if target_id == "p3_startup_failed":
        return w["startup_failed"]

    # Remote job applications (portfolio)
    if target_id in ("p2_l4_remoteUSD", "p2_np_remote"):
        return w["remote_boost"]

    # Root → startup becomes more likely
    if source_id == "root" and target_id == "p1_startup":
        return w["startup_root"]

    return 1.0


def _freelance_profile_multiplier(profile, source_id, target_id):
    """
    Existing freelance profile/reviews dramatically boost
    freelance path success.
    """
    has_profile = bool(profile["has_freelance_profile"])
    if not has_profile:
        return 1.0

    w = _W["freelance_profile"]

    # Root → freelance more likely
    if source_id == "root" and target_id == "p1_freelance":
        return w["root"]

    # Freelance success paths
    if target_id in ("p3_freelance_fulltime", "p4_freelance_premium"):
        return w["success"]
    if target_id == "p3_freelance_side":
        return w["side"]
    if target_id == "p3_freelance_dried":
        return w["dried"]

    # Platform-based freelancing (existing reviews help)
    if target_id == "p2_freelance_platform":
        return w["platform"]

    return 1.0


def _publications_multiplier(profile, source_id, target_id):
    """
    Research publications boost masters admission and
    career advancement in AI/ML roles.
    """
    has_pubs = bool(profile["has_publications"])
    if not has_pubs:
        return 1.0

    w = _W["publications"]

    # Career advancement (research background valued)
    if target_id in ("p1_promoted", "p3_l5_achieved", "p4_motive_staff"):
        return w["career"]

    # Remote job competitiveness (ML research is valued)
    if target_id in ("p2_l4_remoteUSD", "p3_remote_senior", "p4_remote_staff"):
        return w["remote"]

    # Startup AI SaaS (research depth = better product)
    if target_id == "p2_startup_ai_saas":
        return w["startup_ai"]

    return 1.0


def _gpa_multiplier(profile, source_id, target_id):
    """
    GPA affects masters admission probability.
    Masters nodes are dynamic (not in career_nodes), but this
    multiplier is available for future masters edge calibration.
    Also slightly affects career prestige perceptions.
    """
    gpa = profile.get("gpa")
    w = _W["gpa"]

    if gpa is None or w["baseline_low"] <= gpa <= w["baseline_high"]:
        return 1.0  # baseline range

    # Higher GPA → better promotion perception
    if target_id == "p1_promoted":
        if gpa >= 3.8:
            return w["high_promoted"]
        elif gpa <= 2.5:
            return w["low_promoted"]

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
