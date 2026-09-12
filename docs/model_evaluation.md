# Module 8: Model Evaluation & Selection

## 1. Purpose
The purpose of this module is to objectively evaluate the performance of all forecasting models trained in Module 7 on a completely unseen test dataset. We aim to determine the best model for predicting household energy consumption for smart-grid decision support.

## 2. Evaluation Dataset
The models were evaluated using the strict chronological test set holding exactly `4969` records. The test data was kept completely unseen during training, hyperparameter selection, and scaler fitting.

## 3. Models Evaluated
- **Naive Baseline**: Direct shifted prediction.
- **SARIMA**: Statistical auto-regressive model.
- **Random Forest**: Tree ensemble using historical features.
- **XGBoost**: Gradient boosted trees.
- **LSTM**: Recurrent Neural Network using 168-hour lookback.

## 4. Metrics
- **MAE** (Mean Absolute Error): Average absolute difference.
- **RMSE** (Root Mean Squared Error): Penalizes larger errors heavily.
- **MAPE** (Mean Absolute Percentage Error): Relative error.
- **R²**: Coefficient of determination.

## 5. Horizon Evaluation
We evaluated two horizons:
- **Horizon 1**: 1-hour ahead (next hour).
- **Horizon 24**: Recursive 24-hour ahead forecasting.

## 6. Baseline Comparison
Each model was compared against the Naive Baseline. A positive improvement % means the model outperformed the baseline.

## 7. Peak-Demand Evaluation
A smart-grid application must accurately predict demand spikes. We evaluated each model's ability to predict hours where demand exceeded the 90th percentile threshold (`2.28 kWh`).

## 8. Selected Production Model
- **Best Overall Model:** `XGBoost`
- **Rationale:** Lowest RMSE on the 24-hour forecasting horizon.
- **Beats Naive Baseline:** YES

## 9. Evaluation Results

### Horizon 24 Performance
```text
       model      mae     rmse        r2  mae_improvement_vs_naive
        LSTM 0.518844 0.652337  0.091752                 -1.609703
       Naive 0.510624 0.759121 -0.143677                  0.000000
RandomForest 0.373814 0.552091  0.349447                 26.792764
      SARIMA 0.882537 1.073340 -1.458865                -72.834875
     XGBoost 0.332361 0.492360  0.482601                 34.910821
```

### Peak Demand Performance (Horizon 24)
```text
       model  precision   recall  f1_score
        LSTM   0.000000 0.000000  0.000000
       Naive   0.232727 0.233577  0.233151
RandomForest   0.500000 1.000000  0.666667
      SARIMA   0.000000 0.000000  0.000000
     XGBoost   1.000000 1.000000  1.000000
```
