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
*   **Backend**: [FastAPI](https://fastapi.tiangolo.com/) (Python), Pandas, Scikit-learn, XGBoost.
*   **Database & Auth**: [Supabase](https://supabase.com/) (PostgreSQL, Row Level Security, Storage Buckets).
*   **Deployment**: 
    *   Frontend -> **Vercel**
    *   Backend -> **Render**
    *   DB/Storage -> **Supabase**

## 📁 Project Structure

```text
Energy-Consumption-Forecasting/
├── backend/            # FastAPI application (main.py, API routes, ML services)
├── frontend/           # Next.js application (React components, pages)
├── models/             # Serialized ML Models (XGBoost JSON artifacts)
├── data/               # Raw & processed datasets (Ignored in Git)
├── docs/               # Architecture and Deployment documentation
└── tests/              # Pytest backend test suite
```

## 🛠️ Local Development Setup

### 1. Supabase Setup
1. Create a new project on Supabase.
2. Run the provided SQL migrations to create the `uploaded_datasets` and `user_bills` tables.
3. Create a public storage bucket named `energy-csv`.

### 2. Backend (FastAPI)
```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt

# Set up environment variables
export SUPABASE_URL="your-supabase-url"
export SUPABASE_SERVICE_ROLE_KEY="your-secret-key"

# Run the development server
uvicorn main:app --reload --port 8000
```

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
