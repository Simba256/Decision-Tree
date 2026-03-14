"""
Import post-masters career decision tree nodes into the database.
Populates the postmasters_nodes and postmasters_edges tables with career paths
available after completing a master's degree.

The tree models decisions in Years 3-12 (post-graduation) with location-dependent
probabilities for startup success, big tech employment, remote work, and return paths.

Usage: python3 import_postmasters_nodes.py
"""

import sqlite3
import json

from config import DB_PATH, get_logger

logger = get_logger(__name__)

# ═══════════════════════════════════════════════════════════════════════════════
# POST-MASTERS CAREER NODES
#
# Structure:
#   Phase 0: Year 3 (Post-Graduation) - Initial career choice
#   Phase 1: Years 4-6 (Career Development) - Growth within chosen path
#   Phase 2: Years 7-10 (Senior/Founding) - Staff+, founding, or pivot
#   Phase 3: Years 11-12 (Terminal) - Final outcomes
#
# Node types:
#   - employment: Traditional employment (big tech, startup employee)
#   - startup: Startup founding or early-stage employee
#   - remote: Remote work / geo-arbitrage
#   - return: Return to Pakistan
#   - terminal: Final state (no further transitions)
#
# salary_multiplier: Multiplier vs program baseline Y1 salary
# equity_expected_value_usd: Expected equity value in USD (for startup paths)
# requires_location_type: Location requirement (startup_hub, bigtech_hub, any)
# ═══════════════════════════════════════════════════════════════════════════════

POSTMASTERS_NODES = [
    # ═══════════════════════════════════════════════════════════════════════════
    # PHASE 0: YEAR 3 (POST-GRADUATION) - Initial Career Choice
    # ═══════════════════════════════════════════════════════════════════════════
    {
        "id": "pm_root",
        "phase": 0,
        "node_type": "root",
        "label": "Post-Masters\\nCareer Path",
        "salary_multiplier": 1.0,
        "base_probability": 1.0,
        "color": "#00bcd4",
        "note": "Decision point after completing master's degree. Path availability depends on location ecosystem.",
        "children": ["pm_bigtech", "pm_startup_join", "pm_remote_arbitrage", "pm_return_pakistan", "pm_midsize_tech"],
    },
    {
        "id": "pm_bigtech",
        "phase": 0,
        "node_type": "employment",
        "label": "Join FAANG /\\nBig Tech",
        "salary_multiplier": 1.0,
        "base_probability": 0.30,
        "requires_location_type": "bigtech_hub",
        "color": "#4285f4",
        "note": "FAANG/MAANG or equivalent. Requires bigtech presence in market. Strong RSU component.",
        "children": ["pm_bigtech_senior", "pm_bigtech_plateau", "pm_bigtech_to_startup"],
    },
    {
        "id": "pm_startup_join",
        "phase": 0,
        "node_type": "startup",
        "label": "Join Series A-C\\nStartup",
        "salary_multiplier": 0.7,
        "equity_expected_value_usd": 50000,
        "base_probability": 0.20,
        "requires_location_type": "startup_hub",
        "color": "#ff6b6b",
        "note": "Lower base salary but equity upside. Success heavily location-dependent.",
        "children": ["pm_startup_win", "pm_startup_acquihire", "pm_startup_failed"],
    },
    {
        "id": "pm_midsize_tech",
        "phase": 0,
        "node_type": "employment",
        "label": "Join Mid-Size\\nTech Company",
        "salary_multiplier": 0.85,
        "base_probability": 0.25,
        "requires_location_type": None,
        "color": "#a29bfe",
        "note": "Unicorn, public tech company, or well-funded Series D+. Good balance of salary and growth.",
        "children": ["pm_midsize_senior", "pm_midsize_to_bigtech", "pm_midsize_to_startup"],
    },
    {
        "id": "pm_remote_arbitrage",
        "phase": 0,
        "node_type": "remote",
        "label": "Remote for US Co\\nLive Abroad",
        "salary_multiplier": 0.8,
        "base_probability": 0.15,
        "living_cost_location": "chosen",
        "color": "#00ff9f",
        "note": "US salary, lower cost of living location. Requires strong portfolio and negotiation.",
        "children": ["pm_remote_senior", "pm_remote_nomad", "pm_remote_to_onsite"],
    },
    {
        "id": "pm_return_pakistan",
        "phase": 0,
        "node_type": "return",
        "label": "Return to Pakistan\\nwith MS Credential",
        "salary_multiplier": 0.25,
        "base_probability": 0.10,
        "tax_country": "Pakistan",
        "living_cost_location": "Pakistan",
        "color": "#fdcb6e",
        "note": "MS from top program = instant credibility. Can do remote USD or local senior role.",
        "children": ["pm_pk_remote_usd", "pm_pk_local_senior", "pm_pk_founder"],
    },
    # ═══════════════════════════════════════════════════════════════════════════
    # PHASE 1: YEARS 4-6 (CAREER DEVELOPMENT)
    # ═══════════════════════════════════════════════════════════════════════════
    # Big Tech Path
    {
        "id": "pm_bigtech_senior",
        "phase": 1,
        "node_type": "employment",
        "label": "Senior SWE\\nat Big Tech",
        "salary_multiplier": 1.35,
        "base_probability": 0.55,
        "color": "#4285f4",
        "note": "L5/E5/IC5 level. Strong comp, good WLB. Clear path to Staff.",
        "children": ["pm_bigtech_staff", "pm_bigtech_manager", "pm_bigtech_senior_to_founder"],
    },
    {
        "id": "pm_bigtech_plateau",
        "phase": 1,
        "node_type": "employment",
        "label": "Plateau at\\nMid-Level",
        "salary_multiplier": 1.1,
        "base_probability": 0.30,
        "color": "#fab1a0",
        "note": "Stuck at L4/E4. Common path. May need to switch teams or companies.",
        "children": ["pm_bigtech_switch_team", "pm_bigtech_to_midsize", "pm_plateau_to_remote"],
    },
    {
        "id": "pm_bigtech_to_startup",
        "phase": 1,
        "node_type": "startup",
        "label": "Leave for\\nStartup (Vested)",
        "salary_multiplier": 0.75,
        "equity_expected_value_usd": 100000,
        "base_probability": 0.15,
        "color": "#ff6b6b",
        "note": "After 1-year cliff, leave bigtech for startup. Better equity with bigtech credential.",
        "children": ["pm_founder_immediate", "pm_startup_senior"],
    },
    # Mid-Size Tech Path
    {
        "id": "pm_midsize_senior",
        "phase": 1,
        "node_type": "employment",
        "label": "Senior at\\nMid-Size",
        "salary_multiplier": 1.15,
        "base_probability": 0.50,
        "color": "#a29bfe",
        "note": "Senior role with more ownership. Good stepping stone.",
        "children": ["pm_midsize_staff", "pm_midsize_lead"],
    },
    {
        "id": "pm_midsize_to_bigtech",
        "phase": 1,
        "node_type": "employment",
        "label": "Move to\\nBig Tech",
        "salary_multiplier": 1.2,
        "base_probability": 0.25,
        "color": "#4285f4",
        "note": "Leverage mid-size experience to join FAANG at higher level.",
        "children": ["pm_bigtech_senior", "pm_bigtech_plateau"],
    },
    {
        "id": "pm_midsize_to_startup",
        "phase": 1,
        "node_type": "startup",
        "label": "Join Early\\nStartup",
        "salary_multiplier": 0.65,
        "equity_expected_value_usd": 75000,
        "base_probability": 0.25,
        "color": "#ff6b6b",
        "note": "Join seed/Series A with mid-size experience.",
        "children": ["pm_startup_win", "pm_startup_acquihire", "pm_startup_failed"],
    },
    # Startup Employee Path
    {
        "id": "pm_startup_win",
        "phase": 1,
        "node_type": "startup",
        "label": "Startup Exit\\n/ IPO",
        "salary_multiplier": 1.5,
        "equity_expected_value_usd": 200000,
        "base_probability": 0.15,
        "requires_location_type": "startup_hub",
        "color": "#00e676",
        "note": "Company exits or IPOs. Equity pays off. 10-20% of startups in good ecosystems.",
        "children": ["pm_serial_founder", "pm_angel_investor", "pm_bigtech_senior"],
    },
    {
        "id": "pm_startup_acquihire",
        "phase": 1,
        "node_type": "employment",
        "label": "Acqui-hired\\nby Big Co",
        "salary_multiplier": 1.1,
        "equity_expected_value_usd": 30000,
        "base_probability": 0.25,
        "color": "#81ecec",
        "note": "Company acquired for talent. Small equity payout, job at acquirer.",
        "children": ["pm_bigtech_senior", "pm_bigtech_plateau"],
    },
    {
        "id": "pm_startup_failed",
        "phase": 1,
        "node_type": "employment",
        "label": "Startup Failed\\nPivot to Employment",
        "salary_multiplier": 0.9,
        "base_probability": 0.60,
        "color": "#636e72",
        "note": "Most startups fail. Back to job market with valuable experience.",
        "children": ["pm_bigtech_senior", "pm_midsize_senior", "pm_remote_senior"],
    },
    # Remote Path
    {
        "id": "pm_remote_senior",
        "phase": 1,
        "node_type": "remote",
        "label": "Senior Remote\\n(Direct Employment)",
        "salary_multiplier": 1.0,
        "base_probability": 0.55,
        "living_cost_location": "chosen",
        "color": "#00ff9f",
        "note": "Promoted to senior in remote role. Full benefits, equity.",
        "children": ["pm_remote_staff", "pm_remote_settle", "pm_remote_to_onsite"],
    },
    {
        "id": "pm_remote_nomad",
        "phase": 1,
        "node_type": "remote",
        "label": "Digital Nomad\\n(Contract/Freelance)",
        "salary_multiplier": 0.9,
        "base_probability": 0.30,
        "living_cost_location": "chosen",
        "color": "#55efc4",
        "note": "Freelance/contract work. More flexibility, less stability.",
        "children": ["pm_nomad_agency", "pm_nomad_to_employment"],
    },
    {
        "id": "pm_remote_to_onsite",
        "phase": 1,
        "node_type": "employment",
        "label": "Relocate\\nfor Onsite Role",
        "salary_multiplier": 1.15,
        "base_probability": 0.15,
        "color": "#4285f4",
        "note": "Company sponsors relocation. Join onsite with higher comp.",
        "children": ["pm_bigtech_senior", "pm_midsize_senior"],
    },
    # Return to Pakistan Path
    {
        "id": "pm_pk_remote_usd",
        "phase": 1,
        "node_type": "remote",
        "label": "Remote USD\\n+ Pakistan Living",
        "salary_multiplier": 0.5,
        "base_probability": 0.45,
        "tax_country": "Pakistan",
        "living_cost_location": "Pakistan",
        "color": "#00cec9",
        "note": "$60-120K USD remote salary. Extreme arbitrage potential.",
        "children": ["pm_pk_remote_senior", "pm_pk_remote_direct"],
    },
    {
        "id": "pm_pk_local_senior",
        "phase": 1,
        "node_type": "employment",
        "label": "Senior at\\nMNC Pakistan Office",
        "salary_multiplier": 0.35,
        "base_probability": 0.35,
        "tax_country": "Pakistan",
        "living_cost_location": "Pakistan",
        "color": "#fdcb6e",
        "note": "Google, Microsoft, Securiti Pakistan. MS credential = fast track.",
        "children": ["pm_pk_local_staff", "pm_pk_local_to_remote"],
    },
    {
        "id": "pm_pk_founder",
        "phase": 1,
        "node_type": "startup",
        "label": "Found Startup\\nin Pakistan",
        "salary_multiplier": 0.0,
        "equity_expected_value_usd": 25000,
        "base_probability": 0.20,
        "tax_country": "Pakistan",
        "living_cost_location": "Pakistan",
        "color": "#ff6b6b",
        "note": "AI/SaaS for global market or local play. Lower funding but lower costs.",
        "children": ["pm_pk_startup_global", "pm_pk_startup_local", "pm_pk_startup_failed"],
    },
    # ═══════════════════════════════════════════════════════════════════════════
    # PHASE 2: YEARS 7-10 (SENIOR / FOUNDING)
    # ═══════════════════════════════════════════════════════════════════════════
    # Big Tech Terminal
    {
        "id": "pm_bigtech_staff",
        "phase": 2,
        "node_type": "terminal",
        "label": "Staff+ Engineer\\nat Big Tech",
        "salary_multiplier": 2.0,
        "base_probability": 0.35,
        "color": "#4285f4",
        "note": "L6+/E6+/Principal. Top 15% of engineers. $400-600K+ TC.",
        "children": [],
    },
    {
        "id": "pm_bigtech_manager",
        "phase": 2,
        "node_type": "terminal",
        "label": "Engineering\\nManager",
        "salary_multiplier": 1.8,
        "base_probability": 0.25,
        "color": "#4285f4",
        "note": "Management track. People leadership with technical background.",
        "children": [],
    },
    {
        "id": "pm_bigtech_senior_to_founder",
        "phase": 2,
        "node_type": "startup",
        "label": "Leave to\\nFound Company",
        "salary_multiplier": 0.0,
        "equity_expected_value_usd": 150000,
        "base_probability": 0.20,
        "color": "#ff6b6b",
        "note": "Leverage bigtech experience + network to found company. Best founder profile.",
        "children": ["pm_founder_success", "pm_founder_acquihire", "pm_founder_failed"],
    },
    {
        "id": "pm_bigtech_switch_team",
        "phase": 2,
        "node_type": "employment",
        "label": "Switch Team\\nBreak Plateau",
        "salary_multiplier": 1.25,
        "base_probability": 0.50,
        "color": "#4285f4",
        "note": "Internal transfer to break plateau. Common path to Senior.",
        "children": ["pm_bigtech_staff"],
    },
    {
        "id": "pm_bigtech_to_midsize",
        "phase": 2,
        "node_type": "employment",
        "label": "Leave for\\nSenior at Midsize",
        "salary_multiplier": 1.2,
        "base_probability": 0.30,
        "color": "#a29bfe",
        "note": "More ownership and impact at smaller company.",
        "children": ["pm_midsize_staff"],
    },
    {
        "id": "pm_plateau_to_remote",
        "phase": 2,
        "node_type": "remote",
        "label": "Go Remote\\n(Geo Arbitrage)",
        "salary_multiplier": 0.85,
        "base_probability": 0.20,
        "living_cost_location": "chosen",
        "color": "#00ff9f",
        "note": "Leave bigtech for remote with better lifestyle.",
        "children": ["pm_remote_staff"],
    },
    # Mid-Size Terminal
    {
        "id": "pm_midsize_staff",
        "phase": 2,
        "node_type": "terminal",
        "label": "Staff / Principal\\nat Mid-Size",
        "salary_multiplier": 1.6,
        "base_probability": 0.40,
        "color": "#a29bfe",
        "note": "Senior IC track at mid-size. More ownership than bigtech.",
        "children": [],
    },
    {
        "id": "pm_midsize_lead",
        "phase": 2,
        "node_type": "terminal",
        "label": "Tech Lead /\\nEngineering Lead",
        "salary_multiplier": 1.5,
        "base_probability": 0.35,
        "color": "#a29bfe",
        "note": "Technical leadership without full management.",
        "children": [],
    },
    # Founder Path (from bigtech after experience)
    {
        "id": "pm_founder_immediate",
        "phase": 2,
        "node_type": "startup",
        "label": "Found Company\\nImmediately",
        "salary_multiplier": 0.0,
        "equity_expected_value_usd": 100000,
        "base_probability": 0.50,
        "color": "#ff6b6b",
        "note": "Found company on OPT/visa. Higher risk, need entrepreneur visa path.",
        "children": ["pm_founder_success", "pm_founder_acquihire", "pm_founder_failed"],
    },
    {
        "id": "pm_startup_senior",
        "phase": 2,
        "node_type": "startup",
        "label": "Senior at\\nStartup (Pre-IPO)",
        "salary_multiplier": 1.1,
        "equity_expected_value_usd": 80000,
        "base_probability": 0.50,
        "color": "#ff6b6b",
        "note": "Senior role at growth-stage startup. Strong equity potential.",
        "children": ["pm_startup_win", "pm_startup_acquihire"],
    },
    # Remote Terminal
    {
        "id": "pm_remote_staff",
        "phase": 2,
        "node_type": "terminal",
        "label": "Staff / Principal\\n(Remote)",
        "salary_multiplier": 1.3,
        "base_probability": 0.40,
        "living_cost_location": "chosen",
        "color": "#00ff9f",
        "note": "Staff-level remote role. Great comp + lifestyle balance.",
        "children": [],
    },
    {
        "id": "pm_remote_settle",
        "phase": 2,
        "node_type": "terminal",
        "label": "Settle in\\nLCOL Country",
        "salary_multiplier": 0.95,
        "base_probability": 0.35,
        "living_cost_location": "chosen",
        "color": "#55efc4",
        "note": "Permanently settle in low COL location. High savings rate.",
        "children": [],
    },
    {
        "id": "pm_nomad_agency",
        "phase": 2,
        "node_type": "terminal",
        "label": "Build Dev\\nAgency / Studio",
        "salary_multiplier": 1.2,
        "base_probability": 0.25,
        "living_cost_location": "chosen",
        "color": "#55efc4",
        "note": "Build team, take on larger contracts. Entrepreneurial path.",
        "children": [],
    },
    {
        "id": "pm_nomad_to_employment",
        "phase": 2,
        "node_type": "employment",
        "label": "Convert to\\nFull Employment",
        "salary_multiplier": 1.1,
        "base_probability": 0.50,
        "color": "#4285f4",
        "note": "Freelance client converts to full-time role.",
        "children": ["pm_bigtech_senior", "pm_midsize_senior"],
    },
    # Pakistan Terminal
    {
        "id": "pm_pk_remote_senior",
        "phase": 2,
        "node_type": "terminal",
        "label": "Senior Remote\\n$100-150K USD",
        "salary_multiplier": 0.65,
        "base_probability": 0.55,
        "tax_country": "Pakistan",
        "living_cost_location": "Pakistan",
        "color": "#00cec9",
        "note": "Toptal/Turing senior or direct US startup. Extreme savings.",
        "children": [],
    },
    {
        "id": "pm_pk_remote_direct",
        "phase": 2,
        "node_type": "terminal",
        "label": "Direct US Client\\n$120-180K USD",
        "salary_multiplier": 0.8,
        "base_probability": 0.30,
        "tax_country": "Pakistan",
        "living_cost_location": "Pakistan",
        "color": "#00cec9",
        "note": "Direct employment with US startup. Top of PK remote comp.",
        "children": [],
    },
    {
        "id": "pm_pk_local_staff",
        "phase": 2,
        "node_type": "terminal",
        "label": "Staff at\\nPakistan MNC",
        "salary_multiplier": 0.45,
        "base_probability": 0.60,
        "tax_country": "Pakistan",
        "living_cost_location": "Pakistan",
        "color": "#fdcb6e",
        "note": "Staff engineer at Google/MS Pakistan. Top local comp.",
        "children": [],
    },
    {
        "id": "pm_pk_local_to_remote",
        "phase": 2,
        "node_type": "remote",
        "label": "Transition to\\nRemote USD",
        "salary_multiplier": 0.5,
        "base_probability": 0.25,
        "tax_country": "Pakistan",
        "living_cost_location": "Pakistan",
        "color": "#00cec9",
        "note": "Use MNC experience to land remote USD job.",
        "children": ["pm_pk_remote_senior"],
    },
    {
        "id": "pm_pk_startup_global",
        "phase": 2,
        "node_type": "terminal",
        "label": "PK Startup\\nGlobal Market",
        "salary_multiplier": 0.3,
        "equity_expected_value_usd": 50000,
        "base_probability": 0.25,
        "tax_country": "Pakistan",
        "living_cost_location": "Pakistan",
        "color": "#ff6b6b",
        "note": "AI/SaaS targeting global market from Pakistan. Low burn.",
        "children": [],
    },
    {
        "id": "pm_pk_startup_local",
        "phase": 2,
        "node_type": "terminal",
        "label": "PK Startup\\nLocal Market",
        "salary_multiplier": 0.2,
        "equity_expected_value_usd": 20000,
        "base_probability": 0.30,
        "tax_country": "Pakistan",
        "living_cost_location": "Pakistan",
        "color": "#ff6b6b",
        "note": "B2B SaaS or fintech for Pakistan market.",
        "children": [],
    },
    {
        "id": "pm_pk_startup_failed",
        "phase": 2,
        "node_type": "employment",
        "label": "PK Startup Failed\\nJoin Local Tech",
        "salary_multiplier": 0.3,
        "base_probability": 0.45,
        "tax_country": "Pakistan",
        "living_cost_location": "Pakistan",
        "color": "#636e72",
        "note": "Startup didn't work out. Join local company with experience.",
        "children": ["pm_pk_local_senior"],
    },
    # ═══════════════════════════════════════════════════════════════════════════
    # PHASE 3: YEARS 11-12 (TERMINAL OUTCOMES)
    # ═══════════════════════════════════════════════════════════════════════════
    {
        "id": "pm_serial_founder",
        "phase": 3,
        "node_type": "terminal",
        "label": "Serial Founder /\\nVC Backed",
        "salary_multiplier": 0.5,
        "equity_expected_value_usd": 500000,
        "base_probability": 0.30,
        "color": "#ff6b6b",
        "note": "Successful exit enables next venture. 10-50x upside potential.",
        "children": [],
    },
    {
        "id": "pm_angel_investor",
        "phase": 3,
        "node_type": "terminal",
        "label": "Angel Investor /\\nAdvisor",
        "salary_multiplier": 0.3,
        "equity_expected_value_usd": 200000,
        "base_probability": 0.25,
        "color": "#00e676",
        "note": "Use exit proceeds to angel invest. Semi-retired.",
        "children": [],
    },
    {
        "id": "pm_founder_success",
        "phase": 3,
        "node_type": "terminal",
        "label": "Founder:\\nSeries A+ Success",
        "salary_multiplier": 0.8,
        "equity_expected_value_usd": 300000,
        "base_probability": 0.12,
        "color": "#00e676",
        "note": "Company raises Series A+. 5-15% of well-positioned founders.",
        "children": [],
    },
    {
        "id": "pm_founder_acquihire",
        "phase": 3,
        "node_type": "terminal",
        "label": "Founder:\\nAcquired",
        "salary_multiplier": 1.3,
        "equity_expected_value_usd": 100000,
        "base_probability": 0.18,
        "color": "#81ecec",
        "note": "Company acquired. Modest payout + job at acquirer.",
        "children": [],
    },
    {
        "id": "pm_founder_failed",
        "phase": 3,
        "node_type": "terminal",
        "label": "Founder:\\nShut Down",
        "salary_multiplier": 1.2,
        "base_probability": 0.50,
        "color": "#636e72",
        "note": "Company didn't work out. Back to employment with founder experience.",
        "children": [],
    },
]

# ═══════════════════════════════════════════════════════════════════════════════
# POST-MASTERS EDGES
#
# Includes location sensitivity weights:
#   - startup_ecosystem_weight: Multiplied by (ecosystem_strength - 1.0)
#   - bigtech_presence_weight: Multiplied by bigtech modifier
#
# Example: SF startup success
#   base_probability = 0.15
#   startup_ecosystem_weight = 0.5
#   SF ecosystem_strength = 1.8 → modifier = 0.8
#   adjusted_probability = 0.15 * (1 + 0.5 * 0.8) = 0.21
# ═══════════════════════════════════════════════════════════════════════════════

POSTMASTERS_EDGES = [
    # Root to Phase 0
    {"source_id": "pm_root", "target_id": "pm_bigtech", "base_probability": 0.30, "bigtech_presence_weight": 0.4},
    {"source_id": "pm_root", "target_id": "pm_startup_join", "base_probability": 0.20, "startup_ecosystem_weight": 0.3},
    {"source_id": "pm_root", "target_id": "pm_midsize_tech", "base_probability": 0.25},
    {"source_id": "pm_root", "target_id": "pm_remote_arbitrage", "base_probability": 0.15},
    {"source_id": "pm_root", "target_id": "pm_return_pakistan", "base_probability": 0.10},

    # Big Tech Path
    {"source_id": "pm_bigtech", "target_id": "pm_bigtech_senior", "base_probability": 0.55},
    {"source_id": "pm_bigtech", "target_id": "pm_bigtech_plateau", "base_probability": 0.30},
    {"source_id": "pm_bigtech", "target_id": "pm_bigtech_to_startup", "base_probability": 0.15, "startup_ecosystem_weight": 0.3},

    # Big Tech Senior progression
    {"source_id": "pm_bigtech_senior", "target_id": "pm_bigtech_staff", "base_probability": 0.40},
    {"source_id": "pm_bigtech_senior", "target_id": "pm_bigtech_manager", "base_probability": 0.25},
    {"source_id": "pm_bigtech_senior", "target_id": "pm_bigtech_senior_to_founder", "base_probability": 0.20, "startup_ecosystem_weight": 0.4},
    {"source_id": "pm_bigtech_senior", "target_id": "pm_remote_staff", "base_probability": 0.15},

    # Big Tech Plateau recovery
    {"source_id": "pm_bigtech_plateau", "target_id": "pm_bigtech_switch_team", "base_probability": 0.50},
    {"source_id": "pm_bigtech_plateau", "target_id": "pm_bigtech_to_midsize", "base_probability": 0.30},
    {"source_id": "pm_bigtech_plateau", "target_id": "pm_plateau_to_remote", "base_probability": 0.20},

    # Big Tech to Startup transitions
    {"source_id": "pm_bigtech_to_startup", "target_id": "pm_founder_immediate", "base_probability": 0.50, "startup_ecosystem_weight": 0.3},
    {"source_id": "pm_bigtech_to_startup", "target_id": "pm_startup_senior", "base_probability": 0.50},

    # Switch team leads to staff
    {"source_id": "pm_bigtech_switch_team", "target_id": "pm_bigtech_staff", "base_probability": 0.60},
    {"source_id": "pm_bigtech_switch_team", "target_id": "pm_bigtech_manager", "base_probability": 0.40},

    # Bigtech to midsize
    {"source_id": "pm_bigtech_to_midsize", "target_id": "pm_midsize_staff", "base_probability": 0.55},
    {"source_id": "pm_bigtech_to_midsize", "target_id": "pm_midsize_lead", "base_probability": 0.45},

    # Plateau to remote
    {"source_id": "pm_plateau_to_remote", "target_id": "pm_remote_staff", "base_probability": 0.60},
    {"source_id": "pm_plateau_to_remote", "target_id": "pm_remote_settle", "base_probability": 0.40},

    # Mid-Size Tech Path
    {"source_id": "pm_midsize_tech", "target_id": "pm_midsize_senior", "base_probability": 0.50},
    {"source_id": "pm_midsize_tech", "target_id": "pm_midsize_to_bigtech", "base_probability": 0.25, "bigtech_presence_weight": 0.3},
    {"source_id": "pm_midsize_tech", "target_id": "pm_midsize_to_startup", "base_probability": 0.25, "startup_ecosystem_weight": 0.3},

    # Mid-size senior progression
    {"source_id": "pm_midsize_senior", "target_id": "pm_midsize_staff", "base_probability": 0.50},
    {"source_id": "pm_midsize_senior", "target_id": "pm_midsize_lead", "base_probability": 0.35},
    {"source_id": "pm_midsize_senior", "target_id": "pm_bigtech_senior", "base_probability": 0.15, "bigtech_presence_weight": 0.3},

    # Mid-size to bigtech
    {"source_id": "pm_midsize_to_bigtech", "target_id": "pm_bigtech_senior", "base_probability": 0.60},
    {"source_id": "pm_midsize_to_bigtech", "target_id": "pm_bigtech_plateau", "base_probability": 0.40},

    # Mid-size to startup outcomes
    {"source_id": "pm_midsize_to_startup", "target_id": "pm_startup_win", "base_probability": 0.15, "startup_ecosystem_weight": 0.5},
    {"source_id": "pm_midsize_to_startup", "target_id": "pm_startup_acquihire", "base_probability": 0.25},
    {"source_id": "pm_midsize_to_startup", "target_id": "pm_startup_failed", "base_probability": 0.60},

    # Startup Join Path
    {"source_id": "pm_startup_join", "target_id": "pm_startup_win", "base_probability": 0.15, "startup_ecosystem_weight": 0.5},
    {"source_id": "pm_startup_join", "target_id": "pm_startup_acquihire", "base_probability": 0.25, "startup_ecosystem_weight": 0.2},
    {"source_id": "pm_startup_join", "target_id": "pm_startup_failed", "base_probability": 0.60},

    # Startup win outcomes
    {"source_id": "pm_startup_win", "target_id": "pm_serial_founder", "base_probability": 0.30},
    {"source_id": "pm_startup_win", "target_id": "pm_angel_investor", "base_probability": 0.25},
    {"source_id": "pm_startup_win", "target_id": "pm_bigtech_senior", "base_probability": 0.45},

    # Startup acquihire outcomes
    {"source_id": "pm_startup_acquihire", "target_id": "pm_bigtech_senior", "base_probability": 0.60},
    {"source_id": "pm_startup_acquihire", "target_id": "pm_bigtech_plateau", "base_probability": 0.40},

    # Startup failed recovery
    {"source_id": "pm_startup_failed", "target_id": "pm_bigtech_senior", "base_probability": 0.35, "bigtech_presence_weight": 0.3},
    {"source_id": "pm_startup_failed", "target_id": "pm_midsize_senior", "base_probability": 0.40},
    {"source_id": "pm_startup_failed", "target_id": "pm_remote_senior", "base_probability": 0.25},

    # Remote Arbitrage Path
    {"source_id": "pm_remote_arbitrage", "target_id": "pm_remote_senior", "base_probability": 0.55},
    {"source_id": "pm_remote_arbitrage", "target_id": "pm_remote_nomad", "base_probability": 0.30},
    {"source_id": "pm_remote_arbitrage", "target_id": "pm_remote_to_onsite", "base_probability": 0.15},

    # Remote senior progression
    {"source_id": "pm_remote_senior", "target_id": "pm_remote_staff", "base_probability": 0.45},
    {"source_id": "pm_remote_senior", "target_id": "pm_remote_settle", "base_probability": 0.35},
    {"source_id": "pm_remote_senior", "target_id": "pm_bigtech_senior", "base_probability": 0.20, "bigtech_presence_weight": 0.3},

    # Remote nomad progression
    {"source_id": "pm_remote_nomad", "target_id": "pm_nomad_agency", "base_probability": 0.30},
    {"source_id": "pm_remote_nomad", "target_id": "pm_nomad_to_employment", "base_probability": 0.45},
    {"source_id": "pm_remote_nomad", "target_id": "pm_remote_settle", "base_probability": 0.25},

    # Remote to onsite
    {"source_id": "pm_remote_to_onsite", "target_id": "pm_bigtech_senior", "base_probability": 0.50, "bigtech_presence_weight": 0.3},
    {"source_id": "pm_remote_to_onsite", "target_id": "pm_midsize_senior", "base_probability": 0.50},

    # Nomad to employment
    {"source_id": "pm_nomad_to_employment", "target_id": "pm_bigtech_senior", "base_probability": 0.40, "bigtech_presence_weight": 0.3},
    {"source_id": "pm_nomad_to_employment", "target_id": "pm_midsize_senior", "base_probability": 0.60},

    # Return to Pakistan Path
    {"source_id": "pm_return_pakistan", "target_id": "pm_pk_remote_usd", "base_probability": 0.45},
    {"source_id": "pm_return_pakistan", "target_id": "pm_pk_local_senior", "base_probability": 0.35},
    {"source_id": "pm_return_pakistan", "target_id": "pm_pk_founder", "base_probability": 0.20, "startup_ecosystem_weight": 0.2},

    # PK Remote progression
    {"source_id": "pm_pk_remote_usd", "target_id": "pm_pk_remote_senior", "base_probability": 0.60},
    {"source_id": "pm_pk_remote_usd", "target_id": "pm_pk_remote_direct", "base_probability": 0.30},
    {"source_id": "pm_pk_remote_usd", "target_id": "pm_pk_local_senior", "base_probability": 0.10},

    # PK Local progression
    {"source_id": "pm_pk_local_senior", "target_id": "pm_pk_local_staff", "base_probability": 0.60},
    {"source_id": "pm_pk_local_senior", "target_id": "pm_pk_local_to_remote", "base_probability": 0.30},
    {"source_id": "pm_pk_local_senior", "target_id": "pm_pk_founder", "base_probability": 0.10},

    # PK Local to remote
    {"source_id": "pm_pk_local_to_remote", "target_id": "pm_pk_remote_senior", "base_probability": 0.70},
    {"source_id": "pm_pk_local_to_remote", "target_id": "pm_pk_remote_direct", "base_probability": 0.30},

    # PK Founder outcomes
    {"source_id": "pm_pk_founder", "target_id": "pm_pk_startup_global", "base_probability": 0.30},
    {"source_id": "pm_pk_founder", "target_id": "pm_pk_startup_local", "base_probability": 0.30},
    {"source_id": "pm_pk_founder", "target_id": "pm_pk_startup_failed", "base_probability": 0.40},

    # PK startup failed recovery
    {"source_id": "pm_pk_startup_failed", "target_id": "pm_pk_local_senior", "base_probability": 0.70},
    {"source_id": "pm_pk_startup_failed", "target_id": "pm_pk_remote_usd", "base_probability": 0.30},

    # Founder paths (from experienced professionals)
    {"source_id": "pm_bigtech_senior_to_founder", "target_id": "pm_founder_success", "base_probability": 0.15, "startup_ecosystem_weight": 0.5},
    {"source_id": "pm_bigtech_senior_to_founder", "target_id": "pm_founder_acquihire", "base_probability": 0.20},
    {"source_id": "pm_bigtech_senior_to_founder", "target_id": "pm_founder_failed", "base_probability": 0.45},
    {"source_id": "pm_bigtech_senior_to_founder", "target_id": "pm_serial_founder", "base_probability": 0.20, "startup_ecosystem_weight": 0.3},

    # Immediate founder paths
    {"source_id": "pm_founder_immediate", "target_id": "pm_founder_success", "base_probability": 0.10, "startup_ecosystem_weight": 0.5},
    {"source_id": "pm_founder_immediate", "target_id": "pm_founder_acquihire", "base_probability": 0.15},
    {"source_id": "pm_founder_immediate", "target_id": "pm_founder_failed", "base_probability": 0.55},
    {"source_id": "pm_founder_immediate", "target_id": "pm_startup_senior", "base_probability": 0.20},

    # Startup senior outcomes
    {"source_id": "pm_startup_senior", "target_id": "pm_startup_win", "base_probability": 0.25, "startup_ecosystem_weight": 0.4},
    {"source_id": "pm_startup_senior", "target_id": "pm_startup_acquihire", "base_probability": 0.30},
    {"source_id": "pm_startup_senior", "target_id": "pm_startup_failed", "base_probability": 0.45},
]


def import_postmasters_nodes():
    """Import all post-masters nodes into the database."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    inserted = 0
    updated = 0

    for node in POSTMASTERS_NODES:
        children_json = json.dumps(node.get("children") or [])
        cursor.execute(
            """
            INSERT INTO postmasters_nodes (
                id, phase, node_type, label,
                salary_multiplier, equity_expected_value_usd,
                base_probability, requires_location_type,
                living_cost_location, tax_country,
                color, note, children
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                phase = excluded.phase,
                node_type = excluded.node_type,
                label = excluded.label,
                salary_multiplier = excluded.salary_multiplier,
                equity_expected_value_usd = excluded.equity_expected_value_usd,
                base_probability = excluded.base_probability,
                requires_location_type = excluded.requires_location_type,
                living_cost_location = excluded.living_cost_location,
                tax_country = excluded.tax_country,
                color = excluded.color,
                note = excluded.note,
                children = excluded.children
            """,
            (
                node["id"],
                node["phase"],
                node["node_type"],
                node["label"],
                node.get("salary_multiplier", 1.0),
                node.get("equity_expected_value_usd", 0),
                node.get("base_probability", 0.0),
                node.get("requires_location_type"),
                node.get("living_cost_location"),
                node.get("tax_country"),
                node.get("color"),
                node.get("note"),
                children_json,
            ),
        )
        if cursor.rowcount == 1:
            inserted += 1
        else:
            updated += 1

    conn.commit()
    logger.info(
        "Post-masters nodes imported: %d inserted, %d updated", inserted, updated
    )
    return {"nodes_inserted": inserted, "nodes_updated": updated}


def import_postmasters_edges():
    """Import all post-masters edges into the database."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    inserted = 0
    updated = 0

    for edge in POSTMASTERS_EDGES:
        cursor.execute(
            """
            INSERT INTO postmasters_edges (
                source_id, target_id, base_probability,
                startup_ecosystem_weight, bigtech_presence_weight,
                link_type
            ) VALUES (?, ?, ?, ?, ?, 'child')
            ON CONFLICT(source_id, target_id, link_type) DO UPDATE SET
                base_probability = excluded.base_probability,
                startup_ecosystem_weight = excluded.startup_ecosystem_weight,
                bigtech_presence_weight = excluded.bigtech_presence_weight
            """,
            (
                edge["source_id"],
                edge["target_id"],
                edge["base_probability"],
                edge.get("startup_ecosystem_weight", 0.0),
                edge.get("bigtech_presence_weight", 0.0),
            ),
        )
        if cursor.rowcount == 1:
            inserted += 1
        else:
            updated += 1

    conn.commit()
    conn.close()

    logger.info(
        "Post-masters edges imported: %d inserted, %d updated", inserted, updated
    )
    return {"edges_inserted": inserted, "edges_updated": updated}


def import_all():
    """Import both nodes and edges."""
    nodes_result = import_postmasters_nodes()
    edges_result = import_postmasters_edges()
    return {**nodes_result, **edges_result}


if __name__ == "__main__":
    result = import_all()
    print(f"Imported {len(POSTMASTERS_NODES)} post-masters nodes.")
    print(f"Imported {len(POSTMASTERS_EDGES)} post-masters edges.")
    print(f"Result: {result}")
