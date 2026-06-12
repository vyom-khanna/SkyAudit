# SkyAudit 🛰️
## Satellite-Powered Government School Accountability Platform for India

SkyAudit uses Sentinel-2 satellite imagery, census data, and AI to detect fraud and irregularities in India's government school system — ghost schools, enrollment inflation, meal fraud, construction scams, and more.

---

## Architecture

```
skyaudit/
├── backend/          FastAPI + SQLAlchemy + PostGIS
│   ├── app/
│   │   ├── main.py           FastAPI application entry point
│   │   ├── models.py         SQLAlchemy ORM models (8 tables)
│   │   ├── schemas.py        Pydantic request/response schemas
│   │   ├── seed.py           🌱 SEED SCRIPT (generates full demo dataset)
│   │   ├── routers/          API endpoint routers
│   │   │   ├── schools.py    School profile + verification endpoints
│   │   │   ├── districts.py  District profile + rankings
│   │   │   ├── anomalies.py  Anomaly CRUD + officer updates
│   │   │   ├── pulse.py      Live feed + SSE stream
│   │   │   ├── reports.py    PDF reports + national summary
│   │   │   └── auth.py       JWT officer authentication
│   │   ├── services/         Business logic
│   │   │   ├── ghost_detector.py        Module 1
│   │   │   ├── construction_tracker.py  Module 2
│   │   │   ├── enrollment_checker.py    Module 3
│   │   │   ├── meal_verifier.py         Module 4
│   │   │   ├── outcome_authenticator.py Module 5
│   │   │   ├── teacher_presence.py      Module 6
│   │   │   ├── budget_efficiency.py     Module 7
│   │   │   ├── anomaly_engine.py        Orchestrates all 7 modules
│   │   │   ├── satellite.py             Google Earth Engine client
│   │   │   └── scheduler.py             APScheduler periodic jobs
│   │   └── ml/               Machine learning models
│   │       ├── building_detector.py  Open Buildings + NDBI fallback
│   │       ├── change_detection.py   NDBI construction change detection
│   │       ├── enrollment_model.py   Census ceiling computation
│   │       ├── outcome_model.py      XGBoost board result predictor
│   │       └── teacher_risk_model.py Composite teacher risk scorer
│   └── requirements.txt      Python dependencies
│
├── frontend/         React 18 + Tailwind CSS + Leaflet
│   └── src/
│       ├── pages/    Home (India map) | District | School | Pulse | Rankings | Officer
│       ├── components/
│       │   ├── Map/    IndiaMap | DistrictMap | SatelliteViewer (before/after slider)
│       │   ├── Feed/   PulseFeed | AnomalyCard | ResponseTracker
│       │   ├── School/ SchoolCard | ModuleScores | EnrollmentChart
│       │   └── District/ AccountabilityScore gauge | DistrictCard | RankingTable
│       ├── hooks/    useSchool | useDistrict | usePulse | useAnomaly
│       └── utils/    api.js | scoreColors.js | mapUtils.js
│
└── docker-compose.yml  Postgres+PostGIS | FastAPI | React | Redis | Nginx
```

---

## 7 Verification Modules

| # | Module | Method | Weight |
|---|--------|---------|--------|
| 1 | **Ghost School** | Google Open Buildings + NDBI | 25% |
| 2 | **Construction** | Sentinel-2 NDBI change detection | 20% |
| 3 | **Enrollment** | Building capacity + census ceiling | 15% |
| 4 | **Mid-Day Meals** | MDM claims vs verified enrollment | 15% |
| 5 | **Outcomes** | XGBoost predicted vs reported pass rate | 10% |
| 6 | **Teacher Presence** | Composite risk score | 10% |
| 7 | **Budget Efficiency** | Per-child spend vs outcomes | 5% |

---

## Escalation Tracking

The platform tracks the notice and response cycle for verified anomalies, simulating/visualizing the following timeline in the officer's dashboard:
* **Day 0:** Anomaly detected & notice issued to the District Education Officer (DEO).
* **Day 30:** DEO response deadline; flags escalation to the State Education Secretary.
* **Day 60:** Overdue status triggering Right to Information (RTI) auto-filing preview.
* **Day 90:** Listing visibility escalation on the public dashboard.

---

## Quick Start

### Prerequisites
- Docker + Docker Compose
- (Optional) Google Earth Engine service account for live satellite data

### 1. Clone and configure
```bash
cp .env.template .env
# Edit .env with your credentials
# Earth Engine is optional — demo mode uses cached/synthetic data
```

### 2. Start all services
```bash
docker-compose up -d
```

This will:
- Start PostgreSQL with PostGIS extension
- Initialize the database schema
- Run the seed script (500 schools, Sitapur district)
- Start the FastAPI backend on port 8000
- Start the React frontend on port 3000
- Configure Nginx reverse proxy on port 80

### 3. Access the platform
- **Frontend**: http://localhost:3000
- **API docs**: http://localhost:8000/docs
- **Demo login**: `demo@skyaudit.in` / `demo1234`

---

## Manual Setup (without Docker)

### Backend
```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Set up PostgreSQL with PostGIS, then:
export DATABASE_URL=postgresql://user:pass@localhost:5432/skyaudit
python -c "from app.database import init_db; init_db()"
python app/seed.py  # seed data

uvicorn app.main:app --reload --port 8000
```

### Frontend
```bash
cd frontend
npm install
VITE_API_URL=http://localhost:8000 npm run dev
```

---

## API Examples

```bash
# National summary
curl http://localhost:8000/reports/national/summary

# District profile + accountability score
curl http://localhost:8000/districts/09071

# District rankings (top 50 worst)
curl "http://localhost:8000/districts/rankings?limit=50&sort_by=accountability_score"

# School verification report
curl http://localhost:8000/schools/09140100001

# All ghost schools in UP
curl "http://localhost:8000/anomalies/?state=09&anomaly_type=ghost_school&anomaly_status=new"

# Live pulse feed (SSE)
curl -N http://localhost:8000/pulse/stream

# District PDF report
curl http://localhost:8000/reports/district/09071/pdf > report.pdf
```

---

## Data Sources

| Source | Data | Update Frequency |
|--------|------|-----------------|
| UDISE+ | School enrollment, teachers, infrastructure | Annual |
| PM Poshan Portal | Mid-day meal claims | Monthly |
| Sentinel-2 (GEE) | Satellite imagery | 5 days |
| Google Open Buildings | Building footprints | Static |
| Census 2011 (C-13) | School-age population | Decadal + CAGR |
| Samagra Shiksha | Construction grants | As released |
| ASER Reports | Learning outcomes | Annual |
| UP Board (upmsp.edu.in) | Exam pass rates | Annual |
| CAG Reports | Audit findings | Annual |
| Open Budgets India | Education expenditure | Annual |

---

## Scheduler Jobs

| Job | Schedule | Action |
|-----|----------|--------|
| Satellite update | Every 5 days | Re-verify stale schools with new imagery |
| Weekly reports | Monday 6am | Email state reports to pre-configured officials/journalists |

---

## Accountability Score Formula

```python
score = 100 - weighted_penalty

# Penalties by module status:
# ghost   → full penalty (1.0)
# anomaly → 70% penalty
# pending → 30% penalty
# verified → no penalty (0)

# Module weights:
# Ghost Detection:    25%
# Construction:       20%
# Enrollment:         15%
# Mid-Day Meals:      15%
# Outcomes:           10%
# Teachers:           10%
# Budget:              5%
```

---

## License

MIT License — built for public accountability. Pull requests welcome.

---

## Contributing

Priority areas:
1. Add more state board result scrapers (beyond UP)
2. Integrate NAS (National Achievement Survey) data
3. Add DISE historical trend analysis
4. Improve NDBI model with ground-truth validation
5. Hindi/regional language UI translation
