# Career Decision Tree v2 - Database-Driven Architecture

## Architecture Overview

```
┌─────────────────────┐
│     Frontend        │
│   (React App)       │ ← career-tree-v2.html
└─────────┬───────────┘
          │ HTTP Requests
          ↓
┌─────────────────────┐     ┌──────────────────────────────┐
│    Backend API      │     │  Net Worth Calculator V2     │
│   (Flask/Python)    │ ──→ │  - tax_data.py (38 countries)│
│   backend/app.py    │     │  - living_costs.py (79 cities)│
└─────────┬───────────┘     │  - market_mapping.py         │
          │ SQL Queries     │  - networth_calculator.py     │
          ↓                 └──────────────────────────────┘
┌─────────────────────┐
│   SQLite Database   │
│  (career_tree.db)   │ ← 265 programs, 183 universities
└─────────────────────┘
```

---

## File Structure

```
DecisionTree/
├── backend/
│   ├── app.py                    # Flask API server (:5000), 11 endpoints
│   ├── database.py               # Database schema & creation (11 tables)
│   ├── import_data.py            # Excel → Database importer (programs/universities)
│   ├── import_career_nodes.py    # Career nodes importer (4 paths, 100+ nodes)
│   ├── import_reference_data.py  # Tax/living cost/market data → DB importer
│   ├── career_tree.db            # SQLite database (265 programs + reference data)
│   ├── networth_calculator.py    # 12-year net worth calculator V2
│   ├── tax_data.py               # Progressive tax brackets for 38 countries (DB-driven)
│   ├── living_costs.py           # Per-city living costs, 80 cities, 2 tiers (DB-driven)
│   ├── market_mapping.py         # primary_market → location mapping (DB-driven)
│   ├── tests/
│   │   ├── __init__.py
│   │   └── test_all.py           # 102 pytest tests
│   └── README.md
│
├── career-tree-v2.html           # Single-file React frontend (USE THIS)
├── requirements.txt              # Python dependencies
├── Masters_Programs_Global_Rankings.xlsx  # Source data
└── V2_ARCHITECTURE.md            # This file
```

---

## How to Use

### Start the System:

```bash
# 1. Start Backend API
cd backend
python3 app.py

# 2. Open Frontend
# Open career-tree-v2.html in your browser
```

### Run Tests:

```bash
cd backend
python -m pytest tests/ -v
```

### Stop the System:

```bash
kill $(cat backend/api.pid)
```

---

## Database

### Location: `backend/career_tree.db`

### Tables:

**Core data:**
1. **universities** (183 records) — name, country, region, tier
2. **programs** (265 records) — tuition, salaries (Y1/Y5/Y10), field, tier, primary_market
3. **career_nodes** (100+ records) — Career progression tree (4 paths: career, trading, startup, freelance)
4. **outcomes** (empty) — Reserved for future use

**Reference data (DB-driven, editable without code changes):**
5. **exchange_rates** (29 records) — Currency → rate_per_usd (e.g., GBP → 0.79)
6. **tax_brackets** (264 records) — Progressive tax brackets per country/scope, in local currency
7. **tax_config** (114 records) — Key-value store for deductions, social rates, caps, flags per country
8. **living_costs** (80 records) — Per-city annual costs for student/single/family profiles, with frugal (default) and comfortable lifestyle tiers
9. **country_default_cities** (40 records) — Country → default city fallback for living costs
10. **market_mappings** (157 records) — primary_market string → work_country/work_city/us_state
11. **us_region_states** (23 records) — US region keyword → state_code for dynamic market parsing

---

## API Endpoints

All endpoints at `http://localhost:5000/api`

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/programs` | GET | All programs (filterable by field, tier, country, tuition, salary) |
| `/programs/<id>` | GET | Single program details |
| `/universities` | GET | All universities with program counts |
| `/stats` | GET | Summary statistics |
| `/search?q=<query>` | GET | Search programs |
| `/career-nodes` | GET | Career progression tree nodes |
| `/career-nodes/<id>` | GET | Single career node |
| `/networth` | GET | 12yr net worth for all 265 programs |
| `/networth/<id>` | GET | Detailed 12yr net worth for one program |

### Net Worth API Details

```bash
# All programs, compact (no yearly breakdowns)
curl "http://localhost:5000/api/networth?compact=true"

# Comfortable lifestyle tier (default: frugal)
curl "http://localhost:5000/api/networth?compact=true&lifestyle=comfortable"

# Custom family transition year (default: 5; range 1-13, 13=never marry)
curl "http://localhost:5000/api/networth?compact=true&family_year=9"

# Never marry (single costs all 12 years)
curl "http://localhost:5000/api/networth?compact=true&family_year=13"

# Filter by field
curl "http://localhost:5000/api/networth?field=AI/ML&sort_by=net_benefit"

# Filter by work country, limit results
curl "http://localhost:5000/api/networth?work_country=USA&limit=20"

# Override baseline salary (default: $9.5K/yr)
curl "http://localhost:5000/api/networth?baseline_salary=15&compact=true"

# Single program with full yearly breakdown
curl "http://localhost:5000/api/networth/1"

# Single program, comfortable lifestyle
curl "http://localhost:5000/api/networth/1?lifestyle=comfortable"

# Single program, custom family year
curl "http://localhost:5000/api/networth/1?family_year=9"
```

**Query Parameters:**
- `lifestyle` — Living cost tier: "frugal" (default) or "comfortable"
- `family_year` — Calendar year when single→family transition occurs: 1-12, or 13 for "never marry" (default: 5)
- `baseline_salary` — Current annual salary in $K USD (default: 9.5)
- `baseline_growth` — Annual salary growth rate (default: 0.08)
- `sort_by` — net_benefit, cost, y1, y10, networth (default: net_benefit)
- `field` — Filter: AI/ML, CS/SWE, DS, Quant/FE
- `funding_tier` — Filter: tier1_free_europe, tier2_elite_us, etc.
- `work_country` — Filter: USA, United Kingdom, Germany, etc.
- `limit` — Max results
- `compact` — "true" to omit yearly breakdowns

---

## Net Worth Calculator V2

### Design

The calculator computes a **12-year cash accumulation** for each of 265 programs and compares against a **baseline** (staying in Pakistan with current salary).

### Timeline
- **Years 1-2**: Study (pay tuition + student living costs, no income)
- **Years 3-12**: Work (salary grows from Y1→Y5→Y10 data points)
- **Household transition**: Single → family at configurable `family_year` (default: year 5). Year 13 = never marry (single all 12 years). Applies to both masters path and baseline.

### Formula
```
Masters Net Worth = Sum(work years)[after_tax_salary - living_cost]
                  - tuition
                  - Sum(study years)[student_living_cost]

Net Benefit = Masters Net Worth - Baseline Net Worth
```

### Key Components

1. **`tax_data.py`** — Progressive tax brackets for 38 countries including US federal + 11 state brackets + FICA. Social contributions (NI, Sozialversicherung, etc.) where significant. All data parameters (brackets, rates, deductions, caps) loaded from DB at import time; per-country calculation logic stays in Python.

2. **`living_costs.py`** — 80 city entries with 3 profiles (student, single, family) and 2 lifestyle tiers (frugal, comfortable). Country-level fallbacks for 40 countries. Costs loaded from DB at import time. Comfortable tier is ~25-35% above frugal.

3. **`market_mapping.py`** — 157 entries mapping all `primary_market` strings to (work_country, work_city, us_state). Handles complex cases like "India / USA" → India (salary-calibrated), "Canada / USA (reloc)" → USA. Mappings loaded from DB at import time.

4. **`networth_calculator.py`** — Core calculator with salary interpolation, baseline comparison, and comprehensive summary statistics by tier/field/country.

### Key Results (Frugal Lifestyle)
- **170/265 programs** (64%) have positive net benefit vs staying in Pakistan
- **Top**: Baruch MFE (+$2,101K), Princeton MFin (+$1,838K), CMU MSML (+$1,763K)
- **Tier averages**: Elite US ($1,148K), Midtier global ($205K), Asia regional ($96.5K), Free Europe ($74K)

### Lifestyle Tiers

The calculator supports two living cost tiers, selectable via frontend toggle or `?lifestyle=` API param:

| Tier | Description | Impact |
|------|-------------|--------|
| **Frugal** (default) | Outer-area apartment, cook at home, basic social life, no car | ~64% programs positive benefit |
| **Comfortable** | Mid-area apartment, dining out 2x/week, gym membership, some travel | ~45-50% programs positive benefit |

Comfortable costs are ~25-35% above frugal. Examples:
- Bay Area: single $52K→$66K, family $120K→$150K
- London: single $38K→$48K, family $95K→$118K
- Berlin: single $26K→$32K, family $55K→$66K

---

## Current Data

- **265 programs** across **38 countries**
- **183 universities**
- **4 funding tiers**: Free Europe (13), Elite US (17), Midtier Global (165), Asia Regional (70)
- **9 fields**: CS/SWE (147), AI/ML (45), DS (31), Quant/FE (26), plus smaller categories
- **36 distinct work countries** mapped from 155 unique primary_market strings

---

## Frontend Features

- Database-driven interactive decision tree
- Collapsible nodes with path tracking
- Cumulative probability calculation
- Net worth integration: color-coded benefit badges on program nodes
- Lifestyle toggle: switch between frugal and comfortable living cost tiers
- Family year slider: adjust single→family transition (year 1-13, where 13 = never marry)
- Program detail panel showing full financial breakdown
- Career progression paths loaded from API (career, trading, startup, freelance)

---

## Troubleshooting

### Frontend shows "API not responding"
```bash
cd backend && python3 app.py
```

### "Database file not found"
```bash
cd backend
python3 database.py
python3 import_data.py
python3 import_career_nodes.py
python3 import_reference_data.py  # Tax brackets, living costs, market mappings
```

### CORS errors in browser
Ensure `flask-cors` is installed: `pip install flask-cors`

### Port 5000 already in use
```bash
lsof -i :5000
kill -9 <PID>
```
