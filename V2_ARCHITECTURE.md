# Career Decision Tree v2 - Database-Driven Architecture

## ✅ **Setup Complete!**

You now have a **professional, scalable, database-driven** career decision tree system!

---

## 🏗️ **Architecture Overview**

```
┌─────────────────┐
│   Frontend      │
│  (React App)    │ ← career-tree-v2.html
└────────┬────────┘
         │ HTTP Requests
         ↓
┌─────────────────┐
│   Backend API   │
│  (Flask/Python) │ ← backend/app.py
└────────┬────────┘
         │ SQL Queries
         ↓
┌─────────────────┐
│  SQLite Database│
│  (career_tree.db)│ ← backend/career_tree.db
└─────────────────┘
```

---

## 📁 **File Structure**

```
DecisionTree/
├── backend/
│   ├── app.py                 # Flask API server (running on :5000)
│   ├── database.py            # Database schema & creation
│   ├── import_data.py         # Excel → Database importer
│   ├── career_tree.db         # SQLite database (265 programs)
│   ├── api.log               # API server logs
│   ├── api.pid               # API process ID
│   └── README.md             # Backend documentation
│
├── frontend/
│   ├── api.js                # API client functions
│   ├── treeBuilder.js        # Dynamic tree construction
│   ├── CareerTreeV2.jsx      # Main React component
│   └── index.html            # Frontend entry point
│
├── career-tree-v2.html        # Single-file version (USE THIS!)
├── Masters_Programs_Global_Rankings.xlsx  # Source data
└── V2_ARCHITECTURE.md         # This file
```

---

## 🚀 **How to Use**

### **Start the System:**

```bash
# 1. Start Backend API (if not running)
cd backend
python3 app.py

# 2. Open Frontend
# Simply open career-tree-v2.html in your browser
# OR go to: http://localhost:5000 (if you set up frontend serving)
```

### **Stop the System:**

```bash
# Stop API
kill $(cat backend/api.pid)
```

---

## 💾 **Database**

### **Location:** `backend/career_tree.db`

### **Tables:**

1. **universities** (183 records)
   - University details (name, country, region, tier)

2. **programs** (265 records)
   - Full program data (tuition, salaries, ROI, notes)

3. **outcomes** (empty, for future use)
   - Post-graduation paths

4. **career_nodes** (empty, for future use)
   - Original career progression nodes

### **Query Examples:**

```sql
-- Top 10 programs by ROI
SELECT u.name, p.program_name, p.net_10yr_usd
FROM programs p
JOIN universities u ON p.university_id = u.id
ORDER BY p.net_10yr_usd DESC
LIMIT 10;

-- Programs under $50K tuition
SELECT u.name, p.program_name, p.tuition_usd
FROM programs p
JOIN universities u ON p.university_id = u.id
WHERE p.tuition_usd < 50
ORDER BY p.tuition_usd;
```

---

## 🔌 **API Endpoints**

All endpoints available at `http://localhost:5000/api`

| Endpoint | Method | Description | Example |
|----------|--------|-------------|---------|
| `/health` | GET | Health check | `curl http://localhost:5000/api/health` |
| `/programs` | GET | Get all programs (filterable) | `curl http://localhost:5000/api/programs?field=AI/ML` |
| `/programs/<id>` | GET | Get single program | `curl http://localhost:5000/api/programs/1` |
| `/universities` | GET | Get all universities | `curl http://localhost:5000/api/universities` |
| `/stats` | GET | Summary statistics | `curl http://localhost:5000/api/stats` |
| `/search?q=<query>` | GET | Search programs | `curl http://localhost:5000/api/search?q=MIT` |

### **Filter Examples:**

```bash
# All AI/ML programs
curl http://localhost:5000/api/programs?field=AI/ML

# Free European programs
curl http://localhost:5000/api/programs?funding_tier=tier1_free_europe

# Programs under $50K with Y10 salary > $200K
curl "http://localhost:5000/api/programs?max_tuition=50&min_y10_salary=200"

# Search for Stanford
curl http://localhost:5000/api/search?q=Stanford
```

---

## ✨ **Features Implemented**

### **All Original Features:**
- ✅ Collapsible nodes (click − / +)
- ✅ Path selection and tracking
- ✅ Cumulative probability calculation
- ✅ Highlighted subtrees
- ✅ Hover tooltips
- ✅ Phase-based layout
- ✅ Visual design (dark theme, colors, etc.)

### **New Features:**
- ✅ **Database-driven** - No hardcoded nodes
- ✅ **API integration** - Fetch data dynamically
- ✅ **Real-time updates** - Change DB, refresh page
- ✅ **Scalable** - Can add 1000s more programs easily
- ✅ **Queryable** - Filter by field, tier, country, cost, etc.
- ✅ **Maintainable** - Clean separation of concerns

---

## 🎯 **Benefits of This Architecture**

### **Before (v1):**
- ❌ 3500+ lines of hardcoded JavaScript
- ❌ Syntax errors from manual generation
- ❌ Impossible to update without regenerating everything
- ❌ No filtering or search
- ❌ Hard to debug

### **After (v2):**
- ✅ **Clean codebase** - 200 lines of React + API calls
- ✅ **Database-driven** - Update data without touching code
- ✅ **API-powered** - Can build mobile app, CLI, etc.
- ✅ **Searchable** - Find programs instantly
- ✅ **Professional** - Industry-standard architecture
- ✅ **Scalable** - Ready for 10x more data

---

## 📊 **Current Data**

- **265 programs** across **38 countries**
- **183 universities**
- **4 funding tiers**
- **9 fields** (AI/ML, CS/SWE, DS, Quant, etc.)

**By Tier:**
- Tier 1 (Free Europe): 13 programs
- Tier 2 (Elite US): 17 programs
- Tier 3 (Mid-tier Global): 165 programs
- Tier 4 (Asia/Regional): 70 programs

---

## 🔮 **Next Steps / Future Enhancements**

### **Easy Additions:**

1. **Add more career paths to database**
   - Trading/Finance career
   - Startup path
   - Freelancing
   - Career switches

2. **Add post-masters outcomes**
   - Stay abroad vs return
   - PhD paths
   - Salary trajectories

3. **Advanced filters in UI**
   - Filter panel in frontend
   - Cost range sliders
   - Multi-select fields

4. **Analytics dashboard**
   - ROI comparisons
   - Salary visualizations
   - Probability heatmaps

### **Medium Effort:**

5. **User accounts**
   - Save selected paths
   - Track decision progress
   - Compare multiple paths

6. **Export functionality**
   - Export path to PDF
   - Share link to specific path
   - Generate reports

### **Advanced:**

7. **Machine learning**
   - Recommend programs based on profile
   - Predict success probability
   - Optimize for goals

8. **Real-time collaboration**
   - Share with mentors
   - Get feedback on decisions
   - Compare with peers

---

## 🐛 **Troubleshooting**

### **Frontend shows "API not responding"**
```bash
# Check if API is running
ps aux | grep "python3 app.py"

# If not, start it
cd backend
python3 app.py
```

### **"Database file not found"**
```bash
# Recreate database
cd backend
python3 database.py
python3 import_data.py
```

### **CORS errors in browser**
- Make sure API has `flask-cors` installed
- Check that `CORS(app)` is in app.py

### **Port 5000 already in use**
```bash
# Find process using port 5000
lsof -i :5000

# Kill it
kill -9 <PID>
```

---

## 🎉 **Success!**

You've successfully migrated from a **hardcoded 3500-line JavaScript file** to a **clean, database-driven architecture**!

**Key Achievement:**
- From: Unmaintainable spaghetti code
- To: Professional, scalable system

**You can now:**
- ✅ Add programs by updating the database
- ✅ Filter and search easily
- ✅ Build new features on top of the API
- ✅ Scale to 1000s of programs
- ✅ Query data however you want

**This is how real production systems are built!** 🚀
