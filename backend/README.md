# Career Decision Tree - Backend API

## Overview

Flask API serving 265 master's programs from a SQLite database, with a **12-year net worth calculator** that uses progressive tax brackets for ~36 countries, real living costs by city, and a single→family cost transition.

### Database:
- **SQLite** database at `career_tree.db`
- **183 universities**, **265 masters programs** across 38 countries
- **100+ career nodes** with progression paths
- Organized by funding tier, field, and outcomes

### Quick Start:
```bash
cd backend
pip install -r ../requirements.txt
python3 app.py
# API runs at http://localhost:5000
```

### Run Tests:
```bash
cd backend
python3 -m pytest tests/ -v
# 102 tests covering tax, living costs, market mapping, net worth, lifestyle tiers, family transition year
```

---

## API Endpoints

### Core Data

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/health` | Health check → `{"status": "ok"}` |
| GET | `/api/programs` | All programs (with filters) |
| GET | `/api/programs/<id>` | Single program details |
| GET | `/api/universities` | All universities with program counts |
| GET | `/api/stats` | Summary statistics |
| GET | `/api/search?q=<query>` | Search programs by name/uni/field/country |
| GET | `/api/career-nodes` | Career progression tree nodes |
| GET | `/api/career-nodes/<id>` | Single career node |

### Net Worth Calculator

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/networth` | Net worth for all 265 programs |
| GET | `/api/networth?compact=true` | Compact view (id, benefit, rank only) |
| GET | `/api/networth/<id>` | Detailed breakdown for one program |

**Optional networth query parameters:**
- `lifestyle` - Living cost tier: "frugal" (default) or "comfortable"
- `family_year` - Calendar year for single→family transition: 1-12, or 13 for "never marry" (default: 5)
- `baseline_salary` - Override baseline salary in USD thousands (default: 9.5)
- `baseline_growth` - Override annual growth rate (default: 0.08)
- `compact` - Return minimal fields for frontend use

### Program Filter Parameters

`/api/programs` accepts:
- `field` - AI/ML, CS/SWE, DS, Quant/FE
- `funding_tier` - tier1_free_europe, tier2_elite_us, tier3_midtier_global, tier4_asia_regional
- `country` - USA, Germany, etc.
- `max_tuition` - Maximum tuition in USD thousands
- `min_y10_salary` - Minimum year 10 salary in USD thousands

**Examples:**
```bash
# All AI/ML programs
curl http://localhost:5000/api/programs?field=AI/ML

# Net worth for all programs (compact)
curl http://localhost:5000/api/networth?compact=true

# Detailed breakdown for program #42
curl http://localhost:5000/api/networth/42

# Custom baseline salary ($15K/yr, 10% growth)
curl "http://localhost:5000/api/networth?baseline_salary=15&baseline_growth=0.10"

# Comfortable lifestyle tier
curl "http://localhost:5000/api/networth?compact=true&lifestyle=comfortable"

# Custom family transition year (default: 5; range 1-13, 13=never)
curl "http://localhost:5000/api/networth?compact=true&family_year=9"

# Single program, comfortable lifestyle
curl "http://localhost:5000/api/networth/42?lifestyle=comfortable"

# Single program, custom family year
curl "http://localhost:5000/api/networth/42?family_year=13"
```

---

## Net Worth Calculator (V2)

### How It Works

The calculator computes a **12-year cash accumulation** for each program vs. staying in Pakistan:

```
Net Worth = Σ(working years)[after_tax_income - living_cost]
          - tuition
          - Σ(study years)[student_living_cost]
```

**Net Benefit = Program Net Worth - Baseline Net Worth**

### Key Parameters

| Parameter | Value |
|-----------|-------|
| Total window | 12 years (2yr study + 10yr work) |
| Baseline salary | 220K PKR/mo ≈ $9.5K/yr |
| Baseline growth | 8% annually |
| Family transition | Configurable: year 1-12, or 13=never (default: year 5) |
| Salary interpolation | Linear between Y1→Y5→Y10 data points |

### Data Pipeline

1. **Market Mapping** (`market_mapping.py`) — Maps 155 `primary_market` strings to work country, city, and US state. Handles multi-market entries (e.g., "Canada / USA (reloc)" → USA when salary >$100K). Data loaded from `market_mappings` and `us_region_states` DB tables at import time.

2. **Tax Calculation** (`tax_data.py`) — Progressive brackets + social contributions for 38 countries. US federal + 11 state brackets + FICA. All bracket thresholds, deductions, social rates/caps loaded from `exchange_rates`, `tax_brackets`, and `tax_config` DB tables at import time. Per-country calculation logic stays in Python. Entry point: `calculate_annual_tax(gross_usd_k, country, us_state)`.

3. **Living Costs** (`living_costs.py`) — 80 city entries with student/single/family profiles and two lifestyle tiers (frugal, comfortable). Comfortable is ~25-35% above frugal. Country-level fallbacks for 40 countries. Costs transition from single→family at configurable `family_year` (default 5, or 13 for never). Data loaded from `living_costs` and `country_default_cities` DB tables at import time.

4. **Net Worth** (`networth_calculator.py`) — Orchestrates the full 12-year calculation for each program and the Pakistan baseline.

### Sample Results

| Program | Net Benefit |
|---------|------------|
| Baruch MFE | +$2,101K |
| Princeton MFin | +$1,838K |
| CMU MSML | +$1,763K |
| **Tier averages:** | |
| Elite US | +$1,148K |
| Midtier Global | +$205K |
| Asia Regional | +$96.5K |
| Free Europe | +$74K |

186/265 programs (70%) have positive net benefit vs. staying in Pakistan (frugal lifestyle).

### Lifestyle Tiers

Two living cost tiers are available via `?lifestyle=` query parameter:

| Tier | Description | Positive Programs |
|------|-------------|-------------------|
| **Frugal** (default) | Outer-area apt, cook at home, basic social | ~64% |
| **Comfortable** | Mid-area apt, dining out, gym, some travel | ~45-50% |

---

## File Structure

```
backend/
├── app.py                      # Flask API (11 endpoints)
├── career_tree.db              # SQLite database (programs + reference data)
├── database.py                 # DB schema definitions (11 tables)
├── import_data.py              # Excel → SQLite importer (programs/universities)
├── import_career_nodes.py      # Career nodes importer
├── import_reference_data.py    # Reference data → DB importer (tax/costs/markets)
├── market_mapping.py           # primary_market → country/city/state (DB-driven)
├── tax_data.py                 # Progressive tax brackets, 38 countries (DB-driven)
├── living_costs.py             # City/country living costs, 2 tiers (DB-driven)
├── networth_calculator.py      # 12-year net worth engine
└── tests/
    ├── __init__.py
    └── test_all.py             # 102 pytest tests
```

---

## Database Schema

### Core Tables:
1. **universities** — University details (name, country, ranking, etc.)
2. **programs** — Masters program details (tuition, salaries, field, tier, market)
3. **career_nodes** — Career progression tree with phases and probabilities
4. **outcomes** — Post-graduation outcome paths

### Reference Data Tables (DB-driven, editable via SQL):
5. **exchange_rates** (29 rows) — Currency → rate_per_usd
6. **tax_brackets** (264 rows) — Progressive brackets per country/scope, in local currency
7. **tax_config** (114 rows) — Key-value store: deductions, social rates, caps, flags
8. **living_costs** (80 rows) — Per-city annual costs (student/single/family) with frugal + comfortable tiers
9. **country_default_cities** (40 rows) — Country → default city fallback
10. **market_mappings** (157 rows) — primary_market → work_country/city/us_state
11. **us_region_states** (23 rows) — US region keyword → state code

### Re-import Data:
```bash
python3 import_data.py              # Import programs/universities from Excel
python3 import_career_nodes.py      # Import career progression nodes
python3 import_reference_data.py    # Import tax/living cost/market reference data
```

### Example Queries:
```sql
-- Top 10 programs by net benefit
SELECT u.name, p.program_name, p.net_10yr_usd
FROM programs p
JOIN universities u ON p.university_id = u.id
ORDER BY p.net_10yr_usd DESC
LIMIT 10;

-- Average salary by country
SELECT u.country, AVG(p.y10_salary_usd) as avg_salary
FROM programs p
JOIN universities u ON p.university_id = u.id
GROUP BY u.country
ORDER BY avg_salary DESC;
```
