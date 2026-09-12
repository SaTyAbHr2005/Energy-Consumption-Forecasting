# Final Advanced Forecasting Optimization

## 1. Original Performance
- XGBoost 1-H: MAE=0.3195, RMSE=0.4629, R²=0.5747
- XGBoost 24-H: MAE=0.3324, RMSE=0.4924, R²=0.4826

## 2. Feature Improvements
- 65 total features
- Added: extended lags (up to 168h), EWMA (spans 3–48), same-hour 7/14-day averages,
  previous-day profile (total/mean/max/min), seasonal interactions

## 3. XGBoost Tuning
- 3-config search on 1-H; 2-config on 24-H
- Best 1-H val MAE: 0.3556
- Best 24-H val MAE: 0.4822
- log1p target transform applied; metrics reported on original kWh scale

## 4. LSTM
- seq_len=48, units=128, dropout=0.2, EarlyStopping(patience=8)
- Status: val_mae=0.3838

## 5. GRU
- seq_len=48, units=64, dropout=0.2, EarlyStopping(patience=8)
- Status: val_mae=0.3839

## 6. Ensemble
- Weights (XGB/LSTM/GRU): 1.00/0.00/0.00
- Determined on validation data only; test set not seen during weight selection

## 7. Final 1-H Test Results
- **XGBoost-1H:** MAE=0.3089, RMSE=0.4578, R²=0.5841

## 8. Final 24-H Test Results
- XGBoost-24H: MAE=0.4136, RMSE=0.5766, R²=0.3368

## 9. Leakage Controls
- All rolling/EWMA features use shift(1), strictly excluding the current target.
- Same-hour history uses only past-lag values.
- Test set was evaluated exactly once after all decisions were frozen.
- Recursive 24-H forecasting feeds model predictions (not actuals) back in.

## 10. Accuracy Within Tolerance
- ±10%: 20.97%
- ±20%: 40.41%
- ±30%: 56.55%
- ±50%: 76.27%

## 11. Limitations
- Household energy consumption is highly stochastic; 90% R² is not achievable without leakage.
- LSTM/GRU are sequence-only models that cannot exploit the rich calendar/interaction features
  that boost XGBoost.
- The ±10% tolerance accuracy is limited by inherent minute-to-hour variance.
