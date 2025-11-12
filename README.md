# 🛰️ **udigap**

### *Geospatial Connectivity Intelligence Platform for Nigeria*

> **udigap** is a geospatial data engineering and analytics platform that maps, measures, and explains **fiber connectivity and broadband coverage** across Nigeria.
> It fuses **open spatial datasets**, **machine learning**, and **natural language querying** into one intelligent system — enabling planners, engineers, and policymakers to make data-driven infrastructure decisions.

---

## ⚡ **Core Idea**

> Nigeria’s broadband expansion is accelerating, but spatial visibility into who is connected — and who’s left behind — remains fragmented.
> udigap bridges that gap by integrating datasets on **fiber routes**, **population**, **economic activity**, and **public facilities** to produce actionable connectivity insights.

You can ask udigap:

* “Which LGAs in Lagos have the lowest fiber-to-population ratio?”
* “Show me areas with high economic activity but no fiber coverage.”
* “What percentage of schools in Abuja are within 5 km of fiber infrastructure?”
* “Where should we prioritize fiber deployment for maximum economic impact?”

---

## 🧱 **System Architecture**

```
External Datasets (NCC • OSM • GRID3 • VIIRS)
        │
        ▼
ETL Pipeline (Python / AWS Lambda)
        │
        ▼
S3 Data Lake ───────────────► PostgreSQL + PostGIS
        │                           │
        ▼                           ▼
Optional ML Layer ───────────────► FastAPI + LangChain
        │                           │
        ▼                           ▼
Predictions (fiber_priority_zones)  →  Streamlit Dashboard
```

---

## 🗂️ **Repository Structure**

```
udigap/
├── data/             # raw / processed / analytics / parquet layers
├── etl/              # extraction, transformation, and loading scripts
├── ml/               # optional machine learning layer
├── api/              # FastAPI + LangChain NL-to-SQL service
├── dashboard/        # Streamlit web interface
├── sql/              # database schema, indexes, and materialized views
├── docker/           # container setup for API + dashboard + DB
└── tests/            # automated tests
```

---

## ⚙️ **Tech Stack**

| Layer                   | Tools                                         |
| ----------------------- | --------------------------------------------- |
| **Data Processing**     | Python (Pandas, GeoPandas, Shapely)           |
| **Storage**             | AWS S3, PostgreSQL + PostGIS                  |
| **API / Querying**      | FastAPI, LangChain                            |
| **Visualization**       | Streamlit, Folium, Deck.gl                    |
| **Optional ML**         | Scikit-learn, XGBoost, optional Databricks CE |
| **Automation**          | AWS Lambda / Airflow                          |
| **Versioning / DevOps** | Git, DVC, Docker Compose                      |

---

## 🔍 **Features**

| Category                              | Description                                                                                |
| ------------------------------------- | ------------------------------------------------------------------------------------------ |
| 🗺️ **Connectivity Mapping**          | Combines NCC fiber data, OSM routes, and GRID3 population grids to show coverage and gaps. |
| 🤖 **Natural-Language Queries**       | Ask analytical questions in plain English via LangChain + FastAPI.                         |
| 📊 **Spatial Analytics**              | Fiber-to-population ratios, urban-rural differentials, and proximity statistics.           |
| 🧠 **Predictive Insights (Optional)** | Machine-learning models estimate high-impact zones for new fiber deployment.               |
| 🧩 **Extensible Design**              | Easily integrate new data layers like schools, hospitals, or land-cover maps.              |

---

## 💡 **Example Use-Cases**

* **Connectivity Assessment** — Identify underserved LGAs with low fiber-to-population ratios.
* **Infrastructure Planning** — Model where new fiber routes should go for maximum reach.
* **Market Analysis** — Compare operator coverage or broadband growth across states.
* **Policy Decision-Support** — Visualize connectivity inequities for rural development initiatives.

---

## 🚀 **Quick Start**

### **1️⃣ Clone the repo**

```bash
git clone https://github.com/Richardilemon/udigap.git
cd udigap
```

### **2️⃣ Create environment**

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### **3️⃣ Setup PostgreSQL + PostGIS**

```bash
psql -U postgres -c "CREATE DATABASE udigap;"
psql -d udigap -f sql/create_tables.sql
```

### **4️⃣ Run the ETL pipeline**

```bash
python etl/extract_data.py
python etl/transform_data.py
python etl/load_data.py
```

### **5️⃣ Start the API**

```bash
uvicorn api.app:app --reload
```

### **6️⃣ Launch the dashboard**

```bash
streamlit run dashboard/app.py
```

---

## 🧠 **Optional: Machine Learning Layer**

> The ML component predicts where new fiber deployments will yield the highest impact.

```bash
python ml/feature_engineering.py
python ml/train_model.py
python ml/predict_priorities.py
```

Outputs saved to:

* `data/analytics/fiber_priority_zones.geojson`
* `s3://udigap-data/analytics/fiber_priority_zones.parquet`

---

## 🗺️ **Example NL Query**

```bash
POST /nlquery
{
  "question": "Which LGAs in Lagos have the lowest fiber-to-population ratio?"
}
```

**Response**

```json
{
  "query": "SELECT lga_name, SUM(fiber_km)/population AS ratio FROM fiber_population_stats WHERE state='Lagos' GROUP BY lga_name ORDER BY ratio ASC LIMIT 10;",
  "data": [...]
}
```

---

## 🌍 **Future Extensions**

| Module                    | Description                                              |
| ------------------------- | -------------------------------------------------------- |
| 📈 Planning Optimization  | Route cost modeling via NetworkX                         |
| 🧾 Market Analytics       | Operator-level fiber share & demand forecasting          |
| 🧮 Change Detection       | Monitor monthly coverage growth                          |
| 🛰️ Urban Growth Modeling | Integrate Sentinel-2 & GEE data for expansion prediction |

---

## 🧭 **Why udigap Matters**

> By merging **data engineering**, **geospatial intelligence**, and **AI-driven analytics**,
> udigap transforms open infrastructure data into actionable insights that can accelerate Nigeria’s digital inclusion and broadband expansion goals.

---

## 📜 **License**

© 2025 Richard Ilupeju
