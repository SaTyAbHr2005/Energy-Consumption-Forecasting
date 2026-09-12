# Smart Home Energy Consumption Forecasting and Smart-Grid Decision Support Using Big Data Analytics

## Short Project Description
This project aims to forecast household energy consumption and provide smart-grid decision support using Big Data analytics and machine learning techniques. It allows users to upload household electricity consumption data via a web application. The system processes the data, performs analytics, forecasts peak demand using multiple machine learning models, and offers personalized energy insights.

## Problem Statement
Predicting household energy consumption accurately is critical for efficient energy management and grid stability. Fluctuations in energy demand pose challenges for utility providers and end-users. This project addresses the need for scalable and accurate energy consumption forecasting and insights using modern Big Data and Machine Learning approaches.

## Main Objectives
- Build a scalable data pipeline to process and analyze large electricity consumption datasets.
- Implement and evaluate various forecasting models to predict household energy consumption accurately.
- Identify future peak-demand periods to support smart-grid decision making.
- Provide personalized energy insights and recommendations through a user-friendly web interface.

## Planned Technology Stack
- **Python** (Data Science and Scripting)
- **Apache Spark / PySpark** (Big Data Processing)
- **Pandas and NumPy** (Data Manipulation)
- **Scikit-learn, XGBoost, TensorFlow/Keras** (Machine Learning & Deep Learning)
- **FastAPI** (Backend API)
- **Next.js** (Frontend Web Application)
- **PostgreSQL** (Application Database)
- **Parquet** (Large-Scale Data Storage)
- **Git/GitHub** (Version Control)

## Planned Forecasting Models
- Naive baseline
- SARIMA
- Random Forest
- XGBoost
- LSTM
- GRU (Optional)

## Dataset Information
The primary research dataset used for model development and evaluation is the **UCI Individual Household Electric Power Consumption Dataset**.

## Dataset Structure
The project utilizes the UCI Individual Household Electric Power Consumption dataset.

The original UCI dataset contains over 2 million one-minute measurements. PySpark processes the complete raw dataset and aggregates the minute-level measurements into hourly energy observations for forecasting. The forecasting models therefore operate on the resulting hourly time series rather than directly on individual minute records. This preserves the complete historical period while providing a forecasting resolution consistent with the project's daily and weekly temporal features.

- **Source:** [UCI Machine Learning Repository](https://archive.ics.uci.edu/dataset/235/individual%2Bhousehold%2Belectric%2Bpower%2Bconsumption)
- **Description:** Contains over 2 million measurements of electric power consumption in a single household gathered at one-minute intervals over nearly 4 years.
- **Note:** The raw dataset is quite large and is intentionally ignored in version control (.gitignore). Use the provided scripts to download the dataset locally.

## Overall Project Workflow
1. **Module 1:** Project Setup and Dataset Acquisition (Current Status)
2. **Module 2:** Big Data Processing with PySpark
3. **Module 3:** Exploratory Data Analysis (EDA) and Feature Engineering
4. **Module 4:** Model Development and Evaluation
5. **Module 5:** Backend API Development (FastAPI)
6. **Module 6:** Frontend Dashboard Development (Next.js) (Current Status)

## Current Implementation Status
- [x] **Module 1**: Project Setup + Research Dataset
- [x] **Module 2**: User CSV Upload + Validation
- [x] **Module 3**: Big Data Processing with PySpark
- [x] **Module 4**: Data Preprocessing
- [x] **Module 5**: EDA + Energy Analytics
- [x] **Module 6**: Feature Engineering
- [x] **Module 7**: Forecasting Models
- [ ] **Module 8**: Evaluation + Model Selection

Frontend dashboard development is currently underway. The project structure is set up, dataset acquisition, validation, PySpark big data processing, data preprocessing, EDA + energy analytics, feature engineering, and forecasting models have been completed.

### How to Run Module 1
1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```
2. **Download the dataset:**
   ```bash
   python scripts/download_dataset.py
   ```
3. **Inspect the dataset:**
   ```bash
   python scripts/inspect_dataset.py
   ```

### How to Run Module 5
Run exploratory data analytics:
```bash
python scripts/run_eda.py
```
Outputs EDA statistics JSON and analytical figures in `results/`.

### How to Run Module 6
Run the feature engineering pipeline:
```bash
python scripts/create_features.py
```
Outputs the model-ready dataset at `data/processed/forecast_features.parquet`.

### How to Run Module 7
```bash
python scripts/train_forecasting_models.py
```

## Testing
Run unit tests for all modules with:
```bash
   pytest
   ```
   
### User CSV Schema
The user uploaded CSV must have the following required columns:
- `timestamp`: Date and time of the measurement (local time).
- `energy_consumption`: Electricity consumed during the interval in **kWh**.

See `docs/user_csv_format.md` for more details.
