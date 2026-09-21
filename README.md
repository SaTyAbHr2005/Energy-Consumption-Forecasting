# EnergySense ⚡

**Smart Home Energy Consumption Forecasting and Smart-Grid Decision Support**

EnergySense is a full-stack web application designed to help households analyze their historical energy consumption, forecast future demand using Machine Learning (XGBoost), and optimize their electricity usage through Smart Grid load-shifting recommendations. 

*(This project was developed as a Final Year Academic Project).*

---

## 🚀 Features

*   **Data Ingestion**: Upload smart meter CSV data or digitize electricity bills.
*   **Interactive Dashboard**: Visualize daily averages, peak consumption hours, and estimated billing costs.
*   **ML Forecasting**: Predict future household energy demand (1h to 24h horizons) using a pre-trained XGBoost model.
*   **Smart Grid Simulation**: Identify Peak Periods and calculate potential savings by shifting flexible appliances (e.g., EV chargers, HVAC) to off-peak hours.
*   **Actionable Recommendations**: Get personalized, data-driven recommendations to reduce energy waste.

## 🏗️ Architecture & Tech Stack

The application is built using a modern, decoupled architecture, optimized for 100% free-tier cloud deployment.

*   **Frontend**: [Next.js](https://nextjs.org/) (React), Tailwind CSS, Recharts, Lucide Icons.
*   **Backend**: 100% [R](https://www.r-project.org/): [plumber](https://www.rplumber.io/) REST API, XGBoost for R, httr2 (Supabase client). The data + ML pipeline uses [sparklyr](https://spark.posit.co/) (Apache Spark), data.table, ranger and ggplot2.
*   **Database & Auth**: [Supabase](https://supabase.com/) (PostgreSQL, Row Level Security, Storage Buckets).
*   **Deployment**: 
    *   Frontend -> **Vercel**
    *   Backend -> **Render**
    *   DB/Storage -> **Supabase**

## 📁 Project Structure

```text
Energy-Consumption-Forecasting/
├── backend/            # 100% R: run.R + R/ (plumber API), pipeline/ (10-stage data + ML pipeline), tests/
├── frontend/           # Next.js application (React components, pages)
├── models/             # Serialized ML Models (XGBoost JSON artifacts)
├── results/            # Pre-computed metrics / analytics served by the API
├── data/               # Raw & processed datasets (Ignored in Git)
├── docs/               # Architecture and Deployment documentation
├── Dockerfile          # Container image for the API (used by Render)
└── Dockerfile.pipeline # Container image with R + Java + Spark for the pipeline
```

## 🛠️ Local Development Setup

### 1. Supabase Setup
1. Create a new project on Supabase.
2. Run the provided SQL migrations to create the `uploaded_datasets` and `user_bills` tables.
3. Create a public storage bucket named `energy-csv`.

### 2. Backend API (R / plumber)

Requires R 4.1+ (uses the native `|>` pipe). Run everything from the project root.

```bash
# One-time: install the R packages
Rscript backend/install_packages.R   # package list lives in this file (like requirements.txt)

# Put your Supabase credentials in a .env file (see .env.example):
#   SUPABASE_URL=...
#   SUPABASE_SERVICE_ROLE_KEY=...

# Run the API on http://localhost:8000
Rscript backend/run.R

# Self-check (compares the R forecaster with reference values from the original Python model, no Spark needed)
Rscript backend/tests/run_checks.R
```

No R installed? Use Docker instead: `docker build -t energysense-api .` then
`docker run --env-file .env -p 8000:8000 energysense-api`.

### 2b. Data + ML pipeline (R, Spark)

The dataset preparation, model training and analytics that produce `models/final/` and `results/` are also R.
Ten stages, run from the project root:

| Stage | Script | What it does |
|---|---|---|
| 1 | `01_download.R` | Download the UCI household power dataset (2M one-minute rows) |
| 2 | `02_spark_hourly.R` | Spark: minute readings -> hourly kWh |
| 3 | `03_preprocess.R` | Spark: continuous hourly index, gap interpolation, outlier flags |
| 4 | `04_eda.R` | Spark aggregations + ggplot2 figures, `results/analytics/` |
| 5 | `05_features.R` | Spark window functions: baseline feature table |
| 6 | `06_train_models.R` | Naive, SARIMA, Random Forest, XGBoost baselines |
| 7 | `07_evaluate.R` | Test-set metrics, model selection |
| 8 | `08_optimize.R` | Tuned XGBoost 1h / 24h -> `models/final/` (what the API loads) |
| 9 | `09_smart_grid.R` | Peak demand, TOU cost, load-shifting savings |
| 10 | `10_audit.R` | Row-count reconciliation raw -> hourly -> features |

The easiest way to run it (no local R, Java or Spark install) is Docker:

```bash
docker build -f Dockerfile.pipeline -t energysense-pipeline .
docker run --rm -v "$PWD":/app energysense-pipeline Rscript backend/pipeline/run_all.R
# or only some stages, e.g. retrain + evaluate + smart grid:
docker run --rm -v "$PWD":/app energysense-pipeline Rscript backend/pipeline/run_all.R 6 7 8 9
```

Without Docker you need R 4.1+, Java 8/11/17 and these packages:
`Rscript backend/install_packages.R pipeline` (also installs Spark 3.5), then `Rscript backend/pipeline/run_all.R`. A full run takes about 3 minutes.

Tests (the pipeline checks need Spark, so run them in the pipeline image):

```bash
docker run --rm -v "$PWD":/app energysense-pipeline Rscript backend/tests/run_checks.R
docker run --rm -v "$PWD":/app energysense-pipeline Rscript backend/tests/run_pipeline_checks.R
```

Two small CLIs: `Rscript backend/pipeline/inspect_dataset.R` and
`Rscript backend/pipeline/validate_user_csv.R path/to/file.csv`.

### 3. Frontend (Next.js)
```bash
cd frontend
npm install

# Create a .env.local file with:
# NEXT_PUBLIC_SUPABASE_URL=your-supabase-url
# NEXT_PUBLIC_SUPABASE_ANON_KEY=your-anon-key
# NEXT_PUBLIC_API_URL=http://localhost:8000

# Run the development server
npm run dev
```

## 🌐 Deployment
Please refer to [docs/deployment.md](./docs/deployment.md) for a comprehensive step-by-step guide on how to deploy this application to Vercel and Render for free.

## 📝 License
This project was created for academic purposes.
