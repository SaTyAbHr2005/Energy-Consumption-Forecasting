# Module 4: Data Preprocessing

This document outlines the architecture, strategies, and execution steps for the Data Preprocessing module (Module 4) of the Smart Home Energy Consumption Forecasting project.

## Pipeline Architecture

```text
Module 3:
Big Data Processing
        ↓
Module 4:
Data Preprocessing
        ↓
Module 5:
EDA + Energy Analytics
        ↓
Module 6:
Feature Engineering
```

## Purpose

The preprocessing module transforms processed Spark datasets into clean, continuous, and forecasting-ready time-series datasets. It ensures data quality and handles imperfections in the raw data without destroying legitimate patterns (like demand peaks).

## Data Flow

- **Input Dataset:** `data/processed/uci_hourly` (or equivalent hourly Parquet file from Module 3)
- **Output Dataset:** `data/processed/uci_hourly_clean` (Parquet)
- **Report:** `results/metrics/preprocessing_summary.json`

## Preprocessing Steps

### 1. Schema Standardization (User CSV Compatibility)
To support both the UCI dataset and user-uploaded datasets seamlessly, the pipeline checks for user-specific columns like `energy_consumption` and standardizes them to the internal target name `energy_kwh`.

### 2. Timestamp Validation
We drop records with `null` timestamps. We also collect the overall bounds (`min_timestamp` and `max_timestamp`) to define the exact chronological window of the dataset.

### 3. Duplicate Handling
If multiple records exist for the exact same hour, they are grouped and aggregated:
- Total sub-metering and total energy (`energy_kwh`) are **summed**.
- Instantaneous and average features (like voltage and global intensity) are **averaged**.

### 4. Continuous Time-Series Creation (Gap Detection)
Forecasting algorithms generally require evenly spaced, contiguous time steps.
We generate a perfect hourly sequence from `min_timestamp` to `max_timestamp` using Spark's `sequence()` function, and then left-join our data to this sequence. Any missing hours automatically become `null` rows for subsequent handling.

### 5. Missing-Value Strategy
- **Short Gaps (<= 3 hours):** We perform a time-based interpolation by using a Spark `Window` function to fetch the last known value (forward fill) and next known value (backward fill), and computing the average.
- **Long Gaps (> 3 hours):** Blindly interpolating large missing blocks can create fabricated patterns and ruin model training. These gaps are left un-imputed but flagged with a new binary column (`is_long_gap`), which allows downstream models or analytics to decide whether to exclude these windows or apply advanced ML imputation later.

### 6. Outlier Detection
We use the Interquartile Range (IQR) method on the primary target, `energy_kwh`:
- `IQR = Q3 - Q1`
- `Lower Bound = Q1 - 1.5 * IQR`
- `Upper Bound = Q3 + 1.5 * IQR`

**Why legitimate peaks are preserved:**
We do *not* remove or cap outliers. In smart-grid domains, household electricity consumption naturally has extreme legitimate peaks (e.g., turning on multiple appliances at once). Dropping these would erase critical peak-demand information needed for the smart-grid recommendation module. Instead, outliers are preserved and flagged in an `is_energy_outlier` binary column.

### 7. Non-Negative Enforcement
Energy consumption cannot physically be negative. Any sub-zero values are floored to `0.0`.

### 8. Why Scaling Is Not Performed Yet
We intentionally omit transformations like `StandardScaler` or `MinMaxScaler`.
Keeping the data in its original physical units (kWh, Volts, Amps) allows Module 5 (EDA) to produce human-readable and meaningful insights. Scaling is strictly a machine learning preparation step and will be deferred to Module 6 or inside model pipelines.

## Parquet Output
The cleaned data is written in Parquet format. If run on a Windows machine without Hadoop native libraries (`winutils.exe`), the script safely catches the resulting `FileNotFoundException` and falls back to saving via Pandas, since the aggregated dataset easily fits in memory.

## How to Run

Execute the pipeline from the project root:

```bash
python scripts/preprocess_data.py
```
