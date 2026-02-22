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

DB_PATH = Path(__file__).parent / "career_tree.db"

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

    # Root → trading/startup/freelance
    risky_targets = {"p1_trading", "p1_startup", "p1_freelance"}
    # Root → stable career choices
    stable_targets = {"p1_promoted", "p1_notpromoted_stay", "p1_switch_local"}

    if source_id == "root":
        if risk == "high":
            if target_id in risky_targets:
                return 1.4
            if target_id in stable_targets:
                return 0.85
        elif risk == "low":
            if target_id in risky_targets:
                return 0.6
            if target_id in stable_targets:
                return 1.2

    # Within trading path: high risk → more likely to go full-time
    if risk == "high":
        if target_id == "p4_trade_fulltime":
            return 1.3
        if target_id == "p4_trade_quit":
            return 0.7
    elif risk == "low":
        if target_id == "p4_trade_fulltime":
            return 0.7
        if target_id == "p4_trade_quit":
            return 1.3

    # Within startup path: high risk → more likely to scale/fund, less abandon
    if risk == "high":
        if target_id in ("p4_startup_scale", "p3_startup_funded"):
            return 1.2
        if target_id == "p4_startup_abandoned":
            return 0.8
    elif risk == "low":
        if target_id in ("p4_startup_scale", "p3_startup_funded"):
            return 0.8
        if target_id == "p4_startup_abandoned":
            return 1.2

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
            return 1.35
        elif perf == "average":
            return 0.65
        elif perf == "below":
            return 0.35

    # Root → not promoted (inverse)
    if source_id == "root" and target_id == "p1_notpromoted_stay":
        if perf == "top":
            return 0.70
        elif perf == "average":
            return 1.40
        elif perf == "below":
            return 1.70

    # Career advancement: retry promotion
    if target_id == "p3_retry_promoted":
        if perf == "top":
            return 1.30
        elif perf == "average":
            return 0.70
        elif perf == "below":
            return 0.45

    if target_id == "p3_retry_failed_leave":
        if perf == "top":
            return 0.75
        elif perf == "average":
            return 1.25
        elif perf == "below":
            return 1.50

    # Staff/senior promotions
    if target_id in (
        "p3_l5_achieved",
        "p3_local_senior_rise",
        "p4_motive_staff",
        "p4_local_staff",
    ):
        if perf == "top":
            return 1.20
        elif perf == "average":
            return 0.80
        elif perf == "below":
            return 0.60

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
            return 1.25
        elif eng == "intermediate":
            return 0.65
        elif eng == "basic":
            return 0.35

    # Local/stay targets get inverse boost when English is weak
    local_targets = {
        "p2_l4_switchlocal",
        "p2_l4_staymotive",
        "p3_l5_stalled_motive",
        "p4_l4stall_local_sr",
    }
    if target_id in local_targets:
        if eng == "native":
            return 0.90
        elif eng == "intermediate":
            return 1.15
        elif eng == "basic":
            return 1.30

    return 1.0


def _experience_multiplier(profile, source_id, target_id):
    """
    Years of experience affects promotion timelines and remote
    job competitiveness. Baseline is 2.0 years.
    """
    yoe = profile["years_experience"]
    if 1.5 <= yoe <= 2.5:
        return 1.0  # baseline range

    # More experience → higher promotion probability
    if target_id in ("p1_promoted", "p3_retry_promoted", "p2_local_promoted"):
        if yoe >= 5:
            return 1.35
        elif yoe >= 3:
            return 1.15
        elif yoe <= 1:
            return 0.65

    # More experience → better remote job odds
    if target_id in (
        "p2_l4_remoteUSD",
        "p2_np_remote",
        "p3_remote_senior",
        "p4_remote_staff",
    ):
        if yoe >= 5:
            return 1.30
        elif yoe >= 3:
            return 1.10
        elif yoe <= 1:
            return 0.70

    # Less experience → more likely to stagnate
    if target_id in (
        "p2_local_stagnate",
        "p3_teamswitch_stuck",
        "p3_l5_stalled_motive",
    ):
        if yoe >= 5:
            return 0.70
        elif yoe >= 3:
            return 0.85
        elif yoe <= 1:
            return 1.30

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
            return 1.30
        elif savings >= 10000:
            return 1.15
        elif savings <= 2000:
            return 0.60
        elif savings <= 1000:
            return 0.30

    # Startup entry
    if source_id == "root" and target_id == "p1_startup":
        if savings >= 15000:
            return 1.25
        elif savings >= 10000:
            return 1.10
        elif savings <= 2000:
            return 0.65

    # Trading: stocks/options need more capital than crypto
    if source_id == "p1_trading" and target_id == "p2_trade_stocks":
        if savings >= 20000:
            return 1.30
        elif savings <= 3000:
            return 0.60

    if source_id == "p1_trading" and target_id == "p2_trade_crypto":
        if savings <= 1000:
            return 0.70
        elif savings >= 10000:
            return 1.10

    # Trading profitability scales with capital
    if target_id == "p3_trade_profitable":
        if savings >= 20000:
            return 1.20
        elif savings <= 2000:
            return 0.75

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
            return 1.40
        elif quant == "weak":
            return 0.55

    # General trading profitability
    if target_id == "p3_trade_profitable":
        if quant == "strong":
            return 1.20
        elif quant == "weak":
            return 0.80

    # Trading losses
    if target_id == "p3_trade_loss":
        if quant == "strong":
            return 0.75
        elif quant == "weak":
            return 1.35

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
        return 1.30
    if target_id == "p3_startup_failed":
        return 0.75

    # Remote job applications (portfolio)
    if target_id in ("p2_l4_remoteUSD", "p2_np_remote"):
        return 1.15

    # Root → startup becomes more likely
    if source_id == "root" and target_id == "p1_startup":
        return 1.20

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
        return 1.35

    # Freelance success paths
    if target_id in ("p3_freelance_fulltime", "p4_freelance_premium"):
        return 1.40
    if target_id == "p3_freelance_side":
        return 1.15
    if target_id == "p3_freelance_dried":
        return 0.65

    # Platform-based freelancing (existing reviews help)
    if target_id == "p2_freelance_platform":
        return 1.20

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
        return 1.15

    # Remote job competitiveness (ML research is valued)
    if target_id in ("p2_l4_remoteUSD", "p3_remote_senior", "p4_remote_staff"):
        return 1.20

    # Startup AI SaaS (research depth = better product)
    if target_id == "p2_startup_ai_saas":
        return 1.15

    return 1.0


def _gpa_multiplier(profile, source_id, target_id):
    """
    GPA affects masters admission probability.
    Masters nodes are dynamic (not in career_nodes), but this
    multiplier is available for future masters edge calibration.
    Also slightly affects career prestige perceptions.
    """
    gpa = profile.get("gpa")
    if gpa is None or 3.3 <= gpa <= 3.7:
        return 1.0  # baseline range

    # Higher GPA → better promotion perception
    if target_id == "p1_promoted":
        if gpa >= 3.8:
            return 1.10
        elif gpa <= 2.5:
            return 0.90

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
