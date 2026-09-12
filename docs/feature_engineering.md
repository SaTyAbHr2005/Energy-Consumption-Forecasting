# Feature Engineering

## Objective
Module 6 transforms the clean hourly dataset into a structure suitable for predictive forecasting models (Module 7). The features encompass temporal, cyclical, autoregressive (lags), moving averages (rolling), and contextual trend variables, designed completely independently of the underlying forecasting algorithm. 

## Dataset Lineage
* **Source Dataset**: `data/processed/uci_hourly_clean.parquet`
* **Target Feature**: `energy_kwh`
* **Output Dataset**: `data/processed/forecast_features.parquet`

## Feature Groups Overview

| Feature Group | Features | Purpose |
| ------------- | -------- | ------- |
| **Calendar** | `year`, `month`, `day`, `day_of_month`, `day_of_week`, `hour`, `week_of_year`, `quarter` | Captures standard temporal context and cyclic hierarchical bounds. |
| **Weekend** | `is_weekend` | Identifies significant shift in residential power behavior over non-working days. |
| **Cyclical** | `hour_sin`, `hour_cos`, `dow_sin`, `dow_cos`, `month_sin`, `month_cos` | Solves edge-boundary errors for tree/network models by encoding time sequentially (e.g. Hour 23 is mathematically close to Hour 0). |
| **Autoregressive (Lag)** | `lag_1`, `lag_3`, `lag_6`, `lag_12`, `lag_24`, `lag_48`, `lag_72`, `lag_168` | Directly captures historical dependency explicitly aligned to observed patterns in EDA. |
| **Rolling Stats** | `rolling_mean_3`, `rolling_mean_6`, `rolling_mean_12`, `rolling_mean_24`, `rolling_mean_168`, `rolling_std_24`, `rolling_min_24`, `rolling_max_24` | Captures trailing smoothing trends and volatility. These explicitly **exclude** the current target row to prevent leakage. |
| **Trend** | `trend_3h`, `trend_24h` | Represents the immediate velocity/momentum in energy consumption. |
| **Peak Context** | `is_high_demand_previous_hour` | Identifies if the *preceding* hour breached the 90th percentile, acting as an indicator for extended peak periods. |

## EDA-to-Feature Justifications
These features were not chosen arbitrarily; they directly map to findings derived in **Module 5: EDA + Energy Analytics**:

1. **Autocorrelation Evidence (Lags)**
    * **`lag_1`**: Retained because EDA demonstrated a severe 0.72 autocorrelation factor with the immediately preceding hour.
    * **`lag_24`**: Retained because daily seasonality yielded a robust 0.44 autocorrelation factor.
    * **`lag_168`**: Retained because weekly recurrent profiles (same hour last week) also yielded a 0.44 autocorrelation factor.

2. **Consumption Distribution Evidence (Calendar & Peak)**
    * **`is_weekend`**: EDA verified weekend average consumption hits 1.23 kWh, compared to weekday average of 1.04 kWh.
    * **Peak Context**: Peak-demand mapping correctly placed the dataset's 90th percentile at 2.28 kWh, prompting the inclusion of trailing peak flags.

## Safeguards & Leakage Prevention
* **Chronological Integrity**: The dataset enforces ascending timestamps.
* **Leakage Avoidance**: Rolling features were built using precise `rowsBetween(-w_size, -1)` spark windowings. Thus, `rolling_mean_3` averages `t-1`, `t-2`, and `t-3` independently of `t`. 
* **Null Handling**: A 168-hour lag effectively invalidates the first week of modeling data (the burn-in period). Exactly 168 rows are dynamically dropped during creation to ensure no missing values are silently imputed with fake historical data. No `StandardScaler` is applied here to maintain native `kWh` target interpretability for future evaluations.
