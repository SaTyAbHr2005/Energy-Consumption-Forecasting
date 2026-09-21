# Pre-Module 9: Model Optimization

The intermediate optimisation step of the original Python project (an early XGBoost tuning pass that
also compared a recursive and a direct 24-hour model) was **folded into the final optimisation**:
see [final_forecasting_optimization.md](./final_forecasting_optimization.md), produced by
`backend/pipeline/08_optimize.R`. That stage keeps the same methodology:

- Extended leakage-free features (lags up to 168 h, rolling statistics, EWMA, same-hour averages).
- XGBoost with a log1p target and early stopping on the validation set only.
- A direct 24-hour model in addition to the 1-hour model.
- The test set is evaluated exactly once, after every choice is fixed.
