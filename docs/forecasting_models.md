# Module 7: Forecasting Models

## 1. Forecasting Objective
The objective of this module is to implement and train multiple machine learning and statistical models to forecast household electricity consumption. 
By generating multi-model predictions for identical chronological periods, we lay the groundwork for rigorous objective model comparison in Module 8.

## 2. Target Variable
- **Target:** `energy_kwh`
- **Unit:** kWh per hour

## 3. Forecast Horizons
- **1-hour Horizon (t+1):** Predicting the immediate next hour's energy consumption.
- **24-hour Horizon (t+1 to t+24):** Predicting a full 24-hour daily curve into the future.

## 4. Chronological Data Split
To prevent data leakage and evaluate real-world forecasting performance, we strictly use a chronological data split (no random shuffling). 
The dataset was split as follows:
- **70% Training:** Historical data used purely for fitting model parameters.
- **15% Validation:** Sequential data following training, used for early stopping and configuration.
- **15% Test:** Fully held-out future data used exclusively for final evaluation and horizon predictions.

## 5. Model 1: Naive Baselines
- **1-hour Baseline:** Assumes the next hour equals the current hour (`t+1 = t`).
- **24-hour Baseline:** Assumes the next 24 hours equal the exact corresponding hours from the previous day (`t+24 = t`), effectively leveraging the strong daily seasonality (autocorrelation = 0.44) identified in Module 5.

## 6. Model 2: SARIMA
Seasonal Auto-Regressive Integrated Moving Average (SARIMA). 
- Designed to naturally model auto-correlation and explicit daily seasonality.
- We used a lightweight configuration `SARIMA(1,0,0)(1,0,0,24)` fitted on the most recent 2 weeks of training data.
- Naturally supports direct multi-step ahead forecasts for the 24h horizon.

## 7. Model 3: Random Forest
An ensemble of decision trees used to map non-linear relationships.
- Uses purely engineered historical features (lags, rolling stats, cyclical, etc.).
- Does not use raw timestamps or covariates.

## 8. Model 4: XGBoost
Gradient boosted decision trees optimized for speed and performance.
- Capable of modeling complex interactions between context flags (like `is_high_demand_previous_hour`) and trailing lags.

## 9. LSTM / GRU (not part of the R implementation)
The original Python project also trained LSTM and GRU networks, but in the final ensemble they received weight 0: XGBoost alone won. The R implementation therefore compares Naive, SARIMA, Random Forest and XGBoost only.

## 10. Recursive Forecasting Strategy
For models that primarily output 1-step predictions (Random Forest, XGBoost), we implemented a true recursive 24-hour forecasting loop:
1. Predict `t+1` using actual history.
2. Append the predicted value to the local historical sequence.
3. Re-calculate all engineered features (e.g., update `rolling_mean_24`, advance calendar cyclical variables).
4. Predict `t+2` using the dynamically updated features.
5. Repeat 24 times.
This guarantees no future actual targets leak into the multi-step predictions.

## 11. Leakage Prevention
- **Target Separation:** `energy_kwh` is strictly partitioned as the `y` target and excluded from the `X` feature matrix during training.
- **Covariate Exclusion:** Confounding environmental variables from the UCI dataset (`avg_voltage`, `global_intensity`) were stripped from the feature vectors, as their future states would be unknown during true forecasting.
- **Window Safety:** The engineered rolling features exclusively use `ROWS BETWEEN w PRECEDING AND 1 PRECEDING`, guaranteeing the current target hour is ignored in statistical aggregates.

## 12. Model Artifact Storage
Trained model states and prediction outputs are cleanly segregated:
- **Models:** the baseline models are not persisted; the tuned production XGBoost models are saved to `models/final/` by `backend/pipeline/08_optimize.R`.
- **Predictions:** Written in Parquet format to `results/predictions/` (e.g., `xgboost_predictions.parquet`); the XGBoost predictions are also written as `xgboost_predictions.csv`, which the API serves.

## 13. Model Comparison Rationale
Why implement multiple models?
- **Naive:** Sets the absolute minimum performance threshold.
- **SARIMA:** Provides strong parametric baselines relying entirely on linear auto-correlation.
- **Tree-based (RF/XGB):** Excellent at discovering complex non-linear feature interactions without deep network tuning.

## 14. Module 8 Evaluation
Module 7 **does not declare a winner.** 
Its sole responsibility is generating strict, leakage-free predictions for all test horizons. 
Module 8 will load these unified outputs, compute formal metrics (MAE, RMSE, MAPE), and objectively declare the best-performing model for the final Smart Grid integration.
