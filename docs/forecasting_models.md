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

## 9. Model 5: LSTM (Long Short-Term Memory)
A recurrent neural network designed for sequential data.
- **Sequence Length:** 168 hours (1 full week of context).
- **Architecture:** `LSTM(64) -> Dropout(0.2) -> Dense(1)`.
- Models the raw sequential history to infer internal latent state representations.

## 10. Recursive Forecasting Strategy
For models that primarily output 1-step predictions (Random Forest, XGBoost, LSTM), we implemented a true recursive 24-hour forecasting loop:
1. Predict `t+1` using actual history.
2. Append the predicted value to the local historical sequence.
3. Re-calculate all engineered features (e.g., update `rolling_mean_24`, advance calendar cyclical variables).
4. Predict `t+2` using the dynamically updated features.
5. Repeat 24 times.
This guarantees no future actual targets leak into the multi-step predictions.

## 11. LSTM Scaling
Neural networks are sensitive to input magnitude. 
- A `MinMaxScaler` was fitted **exclusively on the training dataset**.
- Validation and test sequences are transformed using this fitted scaler, completely isolating future magnitudes.
- Outputs are inverse-transformed back to raw `kWh` before saving predictions.

## 12. Leakage Prevention
- **Target Separation:** `energy_kwh` is strictly partitioned as the `y` target and excluded from the `X` feature matrix during training.
- **Covariate Exclusion:** Confounding environmental variables from the UCI dataset (`avg_voltage`, `global_intensity`) were stripped from the feature vectors, as their future states would be unknown during true forecasting.
- **Window Safety:** The engineered rolling features exclusively use `rowsBetween(-w, -1)`, guaranteeing the current target hour is ignored in statistical aggregates.

## 13. Model Artifact Storage
Trained model states and prediction outputs are cleanly segregated:
- **Models:** Saved to `models/` (Not strictly written as heavy artifacts to avoid bloat, but structure is enforced).
- **Predictions:** Written in standardized Parquet format to `results/predictions/` (e.g., `results/predictions/xgboost_predictions.parquet`).

## 14. Model Comparison Rationale
Why implement multiple models?
- **Naive:** Sets the absolute minimum performance threshold.
- **SARIMA:** Provides strong parametric baselines relying entirely on linear auto-correlation.
- **Tree-based (RF/XGB):** Excellent at discovering complex non-linear feature interactions without deep network tuning.
- **LSTM:** Excels at extracting long-range temporal dependencies directly from sequence structures.

## 15. Module 8 Evaluation
Module 7 **does not declare a winner.** 
Its sole responsibility is generating strict, leakage-free predictions for all test horizons. 
Module 8 will load these unified outputs, compute formal metrics (MAE, RMSE, MAPE), and objectively declare the best-performing model for the final Smart Grid integration.
