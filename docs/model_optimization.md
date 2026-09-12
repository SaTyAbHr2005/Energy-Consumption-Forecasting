# Pre-Module 9: Model Optimization

## 1. Purpose
Rigorous optimization of the forecasting pipeline before moving to the decision-support web application.

## 2. Methodology
- Extensively expanded features (168-hour lags, EWMA, rolling stats, trend derivations).
- Evaluated Direct Multi-Horizon forecasting for the 24-hour target (predicting t+24 directly).
- Implemented XGBoost with 1000 estimators and early stopping on the validation set.
- Did **NOT** touch the test set during tuning.

## 3. Results (Optimized XGBoost)

### 1-Hour Horizon
- **MAE:** 0.3102
- **RMSE:** 0.4597
- **R²:** 0.5805
- **Accuracy ±10%:** 21.53%
- **Accuracy ±20%:** 40.57%

### 24-Hour Horizon (Direct Forecast)
- **MAE:** 0.4140
- **RMSE:** 0.5768
- **R²:** 0.3364
- **Accuracy ±10%:** 11.61%
- **Accuracy ±20%:** 24.22%

### Peak Detection (24-Hour)
- **Precision:** 0.2000
- **Recall:** 0.0110
- **F1:** 0.0209
