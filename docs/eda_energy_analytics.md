# Exploratory Data Analysis & Energy Analytics

## 1. Overview
This module explores the historical Smart Home Energy Consumption dataset to uncover hourly, daily, weekly, and seasonal patterns, as well as variability and autocorrelation for forecasting.

- **Dataset**: `data/processed/uci_hourly_clean.parquet`
- **Target Variable**: `energy_kwh`
- **Dataset Size**: 34,589 hourly records (approx. 1441.17 total days)
- **Time Range**: 2006-12-16 17:00:00 to 2010-11-26 21:00:00

## 2. Statistical Analysis
- **Mean Consumption**: 1.09 kWh per hour
- **Median Consumption**: 0.77 kWh per hour
- **Maximum Consumption**: 6.56 kWh per hour
- **Minimum Consumption**: 0.03 kWh per hour
- **Coefficient of Variation (CV)**: 0.82 (indicating high variance relative to the mean, demonstrating significant consumption spikes)

## 3. Temporal Patterns
### Hourly Patterns
- **Highest Average Consumption Hour**: 20:00 (8:00 PM) at 1.90 kWh
- **Lowest Average Consumption Hour**: 04:00 (4:00 AM) at 0.44 kWh
- Demand peaks in the late evening, mapping to typical residential presence and activity.

### Weekly & Day-of-Week Patterns
- **Highest Consumption Weekday**: Saturday
- **Lowest Consumption Weekday**: Thursday
- **Weekday vs. Weekend**: Weekend consumption averages 1.23 kWh, whereas weekday consumption averages 1.04 kWh.

### Monthly & Seasonal Patterns
- **Highest Consumption Month**: January (Month 1)
- **Lowest Consumption Month**: August (Month 8)
- Seasonal analysis confirms heating-dominant periods drive heavier consumption profiles than the summer months for this specific household.

## 4. Peak-Demand Methodology
High-demand periods were determined strictly from the dataset distribution rather than arbitrary limits:
- **90th Percentile Threshold**: 2.28 kWh (High Demand)
- **95th Percentile Threshold**: 2.74 kWh (Critical Demand)
- **High Demand Hours**: 1,660 hours
- **Critical Demand Hours**: 2,042 hours

*Note: Outliers observed at the top end (e.g., 6.56 kWh max) were retained during preprocessing to preserve authentic demand surges required for peak forecasting.*

## 5. Sub-metering Analysis
The energy profile decomposes across three explicit sub-meters:
- **Sub-metering 3 (Electric Water Heater & Air Conditioner)**: Dominates the profile, accounting for 72.74% of sub-metered energy.
- **Sub-metering 2 (Laundry Room)**: Contributes 14.62%.
- **Sub-metering 1 (Kitchen)**: Contributes 12.64%.

## 6. Correlational & Autocorrelational Findings
- **Correlation**: `energy_kwh` exhibits a highly linear relationship with `avg_global_active_power` (r = 0.999) and `avg_global_intensity` (r = 0.999), demonstrating strong collinearity.
- **Autocorrelation**: 
  - **Lag 1 (1 hour)**: 0.72 (strong predictive capability from the immediate preceding hour).
  - **Lag 24 (1 day)**: 0.44 (solid daily seasonality).
  - **Lag 168 (1 week)**: 0.44 (solid weekly seasonality).

## 7. Conclusions for Feature Engineering (Module 6)
The EDA provides concrete justification for the feature space of Module 6:
1. **Time Features**: `hour`, `month`, and `dayofweek` will capture the demonstrated cyclical behavior (peaking at 20:00, in January, and on Saturdays).
2. **Lag Features**: Lags at `t-1`, `t-24`, and `t-168` are statistically justified given the autocorrelation peaks.
3. **Categorical Features**: `is_weekend` is fully justified due to the explicit ~20% hike in weekend average demand.
4. **Target Variable**: No scaling was applied here, allowing true `kWh` forecasting.
