# Dataset Usage Audit

## Question 1: Was the complete 2,075,259-row raw dataset processed?
**YES**. The PySpark `SparkProcessor` reads the complete `household_power_consumption.txt` dataset and processes it. Our audit script `audit_dataset.py` confirmed that exactly `2,075,259` raw one-minute records were successfully read, covering the exact period from `2006-12-16 17:24:00` to `2010-11-26 21:02:00`.

## Question 2: Why does the forecasting dataset contain only approximately 33K rows?
The transformation from ~2 million rows to 33,119 feature rows is entirely expected and mathematically correct for the project's goal of **hourly forecasting**.
1. **Minute-to-Hourly Aggregation**: The 2,075,259 one-minute observations were legitimately aggregated into exactly `34,589` hourly observations.
2. **Burn-in & Null History Processing**: The Module 6 feature engineering step generated time-series lags up to 168 hours (1 week). Generating these features for the earliest records results in missing values (burn-in period). Additionally, a known missing chunk of raw data (~420 hours) propagates missing values into future lags. Exactly 1,470 rows were dropped specifically to prevent null-value leakage during model training, leaving precisely `33,119` clean, fully populated feature rows.

## Question 3: How many raw records contribute to the hourly dataset?
The `results/metrics/hourly_aggregation_summary.json` confirms:
- **Raw records**: 2,075,259
- **Expected hourly count**: 34,589
- **Hours with full coverage (60 mins)**: 34,587
- **Hours with partial coverage (<60 mins)**: 2 (First and last boundary hours)
- **Average minutes per hour**: 59.997
The hourly dataset is a perfect 1:1 temporal mapping of the raw data.

## Question 4: Are train/validation/test splits chronological?
**YES**. The `DataSplitter.chronological_split` method strictly divides the `33,119` rows sequentially:
- **Train (70%)**: `23,183` rows. Starts `2006-12-23`.
- **Validation (15%)**: `4,967` rows. Starts immediately after Train ends.
- **Test (15%)**: `4,969` rows. Starts immediately after Validation ends, up to `2010-11-26`.

## Question 5: Was the test set kept unseen?
**YES**. 
- Scaling (for LSTM) is strictly fitted on `train` only.
- Model hyperparameters (RF, XGBoost, SARIMA) are hard-coded or manually defined; the test set was not used for grid search.
- XGBoost and LSTM validation curves are evaluated purely against the `validation` set. The `test` set remains fully unseen until the final prediction loop.

## Question 6: Are there any leakage problems?
**NO**.
- We explicitly excluded raw concurrent covariates (`avg_voltage`, `avg_global_active_power`, `avg_global_intensity`, etc.) from the model features because these values are not known in the future.
- Target `energy_kwh` was strictly separated from the input features.
- Rolling window features used `rowsBetween(-window, -1)` to exclude the current hour's target from its own features.

## Question 7: Are all forecasting models trained correctly?
- **Naive**: Predicts `t+1` and `t+24` purely by shifting historical values. Does not peek into the future.
- **SARIMA**: Fitted correctly on historical data. Does not leak.
- **Random Forest**: Fits against trailing features. Does not use future targets.
- **XGBoost**: Trained purely on historical inputs.
- **LSTM**: Correctly generates 168-hour lookback sequences using only historically trailing data. The 3 epochs used for the current run is sufficient to establish a functioning pipeline, though true convergence may require more epochs (to be tuned later if requested).

## Question 8: Does the current architecture appropriately demonstrate BDA?
**YES**. 
The project clearly demonstrates a Big Data Analytics (BDA) workflow:
1. Distributed read and ingestion of a 2M+ record dataset using **Apache Spark**.
2. Parallel aggregation of minute-level events into standardized hourly analytical blocks.
3. Complex sequential feature generation (rolling windows, trailing lags).
4. Machine Learning on the aggregated dataset.
The fact that the ML models train on ~33K rows instead of 2M rows is a feature of appropriate data engineering—we transformed raw telemetry into a condensed, meaningful time-series framework before modeling.
