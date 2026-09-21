# Module 8: Model Evaluation & Selection

## 1. Purpose
Objectively evaluate every baseline forecasting model on a completely unseen test set and choose the best one for smart-grid decision support.

## 2. Evaluation Dataset
Strict chronological test set; the 24-hour horizon is scored on its last 4969 hours. The test data was never used for training, tuning or scaling.

## 3. Models Evaluated
- **Naive baseline**: previous hour (1h) / same hour previous day (24h).
- **SARIMA(1,0,0)(1,0,0)[24]**: statistical seasonal model, fitted on the last two weeks of training data.
- **Random Forest** (ranger, 50 trees) and **XGBoost**: tree models on the calendar/lag/rolling features.
- LSTM/GRU were dropped in the R port: in the earlier Python project they received weight 0 in the final ensemble.

## 4. Metrics
MAE, RMSE, MAPE and R2.

## 5. Horizons
- **Horizon 1**: next hour.
- **Horizon 24**: recursive 24-hour forecast.

## 6. Baseline comparison
A positive improvement % means the model beat the Naive baseline.

## 7. Peak-demand evaluation
Ability to flag hours above the 90th percentile threshold (2.35 kWh).

## 8. Selected model
- **Best model:** `XGBoost`
- **Rationale:** Lowest RMSE on the 24-hour forecasting horizon.
- **Beats naive baseline:** YES

## 9. Results

### Horizon 24
```text
        model    mae   rmse      r2 mae_improvement_vs_naive
        Naive 0.5106 0.7591 -0.1437                     0.00
 RandomForest 0.3552 0.5215  0.4196                    30.45
       SARIMA 0.8875 1.0779 -1.4799                   -73.81
      XGBoost 0.3063 0.4912  0.4851                    40.02
```

### Peak demand (Horizon 24)
```text
        model precision recall f1_score
        Naive    0.2241  0.225   0.2245
 RandomForest    0.0000  0.000   0.0000
       SARIMA    0.0000  0.000   0.0000
      XGBoost    1.0000  1.000   1.0000
```
