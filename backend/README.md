# Career Decision Tree - Backend API

## ✅ Setup Complete!

### Database:
- **SQLite** database at `career_tree.db`
- **183 universities**
- **265 masters programs** across 38 countries
- Organized by funding tier, field, and outcomes

### API Running:
- **URL:** http://localhost:5000
- **Status:** Running (PID in `api.pid`)

---

## 📚 API Endpoints

### 1. Health Check
```bash
GET /api/health
```
Returns: `{"status": "ok"}`

### 2. Get All Programs (with filters)
```bash
GET /api/programs
```

**Optional query parameters:**
- `field` - Filter by field (AI/ML, CS/SWE, DS, Quant/FE)
- `funding_tier` - tier1_free_europe, tier2_elite_us, tier3_midtier_global, tier4_asia_regional
- `country` - Filter by country (USA, Germany, etc.)
- `max_tuition` - Maximum tuition in USD (thousands)
- `min_y10_salary` - Minimum year 10 salary (thousands)

**Examples:**
```bash
# All AI/ML programs
curl http://localhost:5000/api/programs?field=AI/ML

# Free European programs
curl http://localhost:5000/api/programs?funding_tier=tier1_free_europe

# Programs under $50K tuition
curl http://localhost:5000/api/programs?max_tuition=50

# High-salary programs (Y10 > $200K)
curl http://localhost:5000/api/programs?min_y10_salary=200
```

### 3. Get Single Program
```bash
GET /api/programs/<id>
```

### 4. Get All Universities
```bash
GET /api/universities
```
Returns all universities with program counts

### 5. Get Statistics
```bash
GET /api/stats
```
Returns summary stats (counts by tier, field, country, salary ranges)

### 6. Search
```bash
GET /api/search?q=<query>
```
Search programs by university, program name, field, or country

**Examples:**
```bash
# Find MIT programs
curl http://localhost:5000/api/search?q=MIT

# Find ML programs
curl http://localhost:5000/api/search?q=machine

# Find German universities
curl http://localhost:5000/api/search?q=Germany
```

---

## 🚀 Running the API

### Start:
```bash
cd backend
python3 app.py
```

### Stop:
```bash
kill $(cat api.pid)
```

### Restart:
```bash
kill $(cat api.pid)
python3 app.py > api.log 2>&1 &
echo $! > api.pid
```

---

## 🗄️ Database Schema

### Tables:
1. **universities** - University details
2. **programs** - Masters program details
3. **outcomes** - Post-graduation outcome paths (to be populated)
4. **career_nodes** - Original career progression nodes (to be populated)

### Re-import Data:
```bash
python3 import_data.py
```

---

## 📊 Database Queries (Examples)

```sql
-- Top 10 programs by ROI
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

-- Programs by field and tier
SELECT p.funding_tier, p.field, COUNT(*) as count
FROM programs p
GROUP BY p.funding_tier, p.field
ORDER BY p.funding_tier, count DESC;
```

---

## 🔧 Next Steps

1. ✅ Database created and populated
2. ✅ API running with all endpoints
3. ⏳ Update React frontend to fetch from API
4. ⏳ Add career progression nodes to database
5. ⏳ Add post-masters outcome paths

---

## 🎯 Benefits of This Architecture

✅ **Clean separation** - Data vs. UI logic
✅ **Easy updates** - Just update database, no code changes
✅ **Powerful queries** - Filter, search, aggregate easily
✅ **Scalable** - Can add 1000s more programs
✅ **Reusable API** - Can build mobile app, CLI tool, etc.
✅ **Professional** - Industry-standard architecture
