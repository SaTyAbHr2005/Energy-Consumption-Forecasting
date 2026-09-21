# Final Advanced Forecasting Optimization

## 1. Baseline performance (untuned XGBoost, Module 7)
- 1-H: MAE=0.3200, RMSE=0.4619, R2=0.5765
- 24-H: MAE=0.3063, RMSE=0.4912, R2=0.4851

## 2. Features
- 65 features: calendar/cyclical, lags up to 168 h, rolling stats, EWMA (spans 3-48), same-hour averages, previous-day profile.

## 3. XGBoost tuning
- 3-config search for 1-H and 2-config search for 24-H, chosen on validation MAE with early stopping.
- Best 1-H validation MAE: 0.3561; best 24-H: 0.4816
- The target is log1p-transformed; all metrics are reported on the original kWh scale.

## 4. Deep learning
LSTM/GRU are not part of the R port: the Python project's final ensemble gave them weight 0, so XGBoost alone is the production model.

## 5. Final 1-H test results
- **XGBoost-1H:** MAE=0.3090, RMSE=0.4580, R2=0.5837

## 6. Final 24-H test results
- XGBoost-24H (direct): MAE=0.4145, RMSE=0.5777, R2=0.3341

## 7. Leakage controls
- Every rolling/EWMA feature excludes the current target (series shifted by one hour).
- Same-hour history uses only past lags.
- The test set was evaluated exactly once, after all decisions were frozen.

## 8. Accuracy within tolerance
- +/-10%: 21.63%
- +/-20%: 40.39%
- +/-30%: 56.19%
- +/-50%: 76.45%

## 9. Limitations
- Household consumption is highly stochastic; R2 above 0.9 is not achievable without leakage.
- Accuracy within +/-10% is limited by inherent minute-to-hour variance.
