# Stage 8: final advanced forecasting. Leakage-free features, tuned XGBoost (1-hour and 24-hour
# direct), evaluated ONCE on the test set. Writes the production models to models/final/ and
# results/metrics/final_selected_model.json, which the API loads.
source("backend/pipeline/R/common.R")
source("backend/pipeline/R/models.R")
library(ggplot2)

banner("Final advanced forecasting optimization")
raw <- read_parquet_file(CLEAN_FILE)[c("timestamp", "energy_kwh")]
split_info <- read_json_file(file.path(METRICS, "data_split.json"))
p90 <- read_json_file(file.path(METRICS, "eda_summary.json"))$peak_demand_analysis$percentile_90_threshold

# --- target distribution report ---------------------------------------------------------
tgt <- raw$energy_kwh[!is.na(raw$energy_kwh)]
q <- function(p) quantile(tgt, p, names = FALSE)
write_json_file(list(count = length(tgt), mean = mean(tgt), median = median(tgt), std = sd(tgt), skewness = skewness(tgt),
                     zeros = sum(tgt == 0), near_zero_lt005 = sum(tgt < 0.05), p5 = q(.05), p25 = q(.25), p75 = q(.75),
                     p90 = q(.90), p95 = q(.95), p99 = q(.99), max = max(tgt), min = min(tgt)),
                file.path(METRICS, "target_distribution.json"))
cat(sprintf("Target: mean=%.3f median=%.3f skew=%.3f\n", mean(tgt), median(tgt), skewness(tgt)))

# --- features: same timestamps as the basic feature table -----------------------------------
cat("\n[1] Building the advanced feature set...\n")
feat <- build_features(raw, p90)
orig_ts <- read_parquet_file(FEATURES_FILE)["timestamp"]
feat <- locf_zero(merge(orig_ts, feat, by = "timestamp", all.x = TRUE, sort = TRUE))

train_end <- parse_ts(split_info$train_end)
val_end <- parse_ts(split_info$validation_end)
train <- feat[feat$timestamp <= train_end, ]
val <- feat[feat$timestamp > train_end & feat$timestamp <= val_end, ]
test <- feat[feat$timestamp > val_end, ]
feat_cols <- feature_columns(feat)
cat(sprintf("Splits: train %d, val %d, test %d; %d features\n", nrow(train), nrow(val), nrow(test), length(feat_cols)))

# --- XGBoost 1-hour: small hyper-parameter search on validation MAE -----------------------------
cat("\n[2] XGBoost 1-hour search (validation MAE)\n")
xgb_cfg <- function(eta, depth, mcw, sub, col, gamma, alpha, lambda) {
  list(eta = eta, max_depth = depth, min_child_weight = mcw, subsample = sub, colsample_bytree = col,
       gamma = gamma, alpha = alpha, lambda = lambda)
}
search <- function(grid, X_tr, y_tr, X_val, y_val) {
  best <- NULL
  for (i in seq_along(grid)) {
    fit <- train_xgb(X_tr, y_tr, X_val, y_val, grid[[i]])
    cat(sprintf("    config %d: validation MAE = %.4f\n", i, fit$val_mae))
    if (is.null(best) || fit$val_mae < best$val_mae) best <- fit
  }
  best
}
best_1h <- search(list(xgb_cfg(0.02, 6, 3, 0.80, 0.80, 0.0, 0.10, 1.0),
                       xgb_cfg(0.01, 5, 5, 0.85, 0.75, 0.1, 0.05, 2.0),
                       xgb_cfg(0.03, 7, 3, 0.75, 0.85, 0.0, 0.00, 0.5)),
                  train[feat_cols], train$energy_kwh, val[feat_cols], val$energy_kwh)
xgboost::xgb.save(best_1h$model, file.path(MODELS, "xgboost_1h.json"))

# --- XGBoost 24-hour direct (target = energy 23 rows ahead, as in the original) -------------------
cat("\n[3] XGBoost 24-hour direct\n")
with_target <- function(d) {
  d$tgt24 <- c(d$energy_kwh[-seq_len(23)], rep(NA_real_, 23))
  d[!is.na(d$tgt24), ]
}
tr24 <- with_target(train); va24 <- with_target(val); te24 <- with_target(test)
best_24h <- search(list(xgb_cfg(0.01, 6, 5, 0.80, 0.80, 0.1, 0.10, 2.0),
                        xgb_cfg(0.02, 5, 3, 0.85, 0.75, 0.0, 0.05, 1.0)),
                   tr24[feat_cols], tr24$tgt24, va24[feat_cols], va24$tgt24)
xgboost::xgb.save(best_24h$model, file.path(MODELS, "xgboost_24h_direct.json"))

# --- final test evaluation: once, after every choice above was fixed ------------------------------
cat("\n[4] Final test evaluation\n")
pred_1h <- xgb_predict(best_1h$model, test[feat_cols])
pred_24h <- xgb_predict(best_24h$model, te24[feat_cols])
m1 <- full_metrics(test$energy_kwh, pred_1h, "XGBoost-1H")
m24 <- full_metrics(te24$tgt24, pred_24h, "XGBoost-24H")
pk <- peak_metrics(test$energy_kwh, pred_1h, p90)
pk$precision <- pk$true_positives / (pk$true_positives + pk$false_positives + 1e-9)

imp <- as.data.frame(xgboost::xgb.importance(model = best_1h$model))
imp <- data.frame(feature = imp$Feature, gain = imp$Gain)
write_csv_file(imp, file.path(METRICS, "advanced_feature_importance.csv"))

# original (baseline) XGBoost from the model comparison
cmp <- utils::read.csv(file.path(METRICS, "model_comparison.csv"))
orig <- function(h) cmp[cmp$model == "XGBoost" & cmp$horizon == h, ]
o1 <- orig(1); o24 <- orig(24)

# --- figures ------------------------------------------------------------------------------------
save_plot(ggplot(head(imp, 20), aes(gain, reorder(feature, gain))) + geom_col(fill = "#2171b5") +
            labs(title = "Top-20 Feature Importances (XGBoost 1-H)", x = "Gain", y = NULL) + theme_energy(),
          "advanced_feature_importance.png", dir = file.path(FIGURES, "final_opt"), height = 8)
win <- seq_len(min(336, nrow(test)))
long <- rbind(data.frame(timestamp = test$timestamp[win], kind = "Actual", kwh = test$energy_kwh[win]),
              data.frame(timestamp = test$timestamp[win], kind = "XGBoost-1H", kwh = pred_1h[win]))
save_plot(ggplot(long, aes(timestamp, kwh, color = kind)) + geom_line(alpha = 0.8) +
            labs(title = "Actual vs Predicted - XGBoost-1H (first 2 weeks of test)", x = NULL, y = "kWh", color = NULL) + theme_energy(),
          "optimized_actual_vs_predicted.png", dir = file.path(FIGURES, "final_opt"), width = 14, height = 5)
res <- test$energy_kwh - pred_1h
save_plot(ggplot(data.frame(res), aes(res)) + geom_histogram(bins = 60, fill = "steelblue") +
            labs(title = "Residual Distribution - XGBoost-1H", x = "Error (Actual - Predicted)") + theme_energy(),
          "optimized_residual_distribution.png", dir = file.path(FIGURES, "final_opt"))
err_hour <- aggregate(ae ~ hour, data.frame(hour = test$hour, ae = abs(res)), mean)
save_plot(ggplot(err_hour, aes(factor(hour), ae)) + geom_col(fill = "#2171b5") +
            labs(title = "Mean Absolute Error by Hour - Best Model", x = "Hour", y = "MAE") + theme_energy(),
          "optimized_error_by_hour.png", dir = file.path(FIGURES, "final_opt"), height = 4)
save_plot(ggplot(data.frame(model = c("Baseline XGBoost", "Optimized"), mae = c(o1$mae, m1$mae)), aes(model, mae)) +
            geom_col(fill = c("#6baed6", "#2171b5")) + labs(title = "MAE: Baseline vs Optimized (1-H)", x = NULL, y = "MAE (kWh)") +
            theme_energy(), "before_after_mae.png", dir = file.path(FIGURES, "final_opt"), width = 6, height = 4)
tols <- c(0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.40, 0.50)
acc <- data.frame(tol = factor(sprintf("+/-%d%%", round(tols * 100)), sprintf("+/-%d%%", round(tols * 100))),
                  pct = vapply(tols, function(t) acc_within(test$energy_kwh, pred_1h, t), 0))
save_plot(ggplot(acc, aes(tol, pct, group = 1)) + geom_line() + geom_point() + geom_hline(yintercept = 90, color = "red", linetype = "dashed") +
            labs(title = "Accuracy Within Tolerance - XGBoost-1H", x = NULL, y = "% predictions within tolerance") + theme_energy(),
          "accuracy_within_tolerance.png", dir = file.path(FIGURES, "final_opt"), width = 8, height = 5)

# --- result files ---------------------------------------------------------------------------------
comp <- rbind(as.data.frame(m1), as.data.frame(m24))
comp$horizon <- c("1H", "24H")
write_csv_file(comp, file.path(METRICS, "final_advanced_model_comparison.csv"))
write_csv_file(data.frame(model = "XGBoost", horizon = c("1H", "24H"),
                          original_mae = c(o1$mae, o24$mae), optimized_mae = c(m1$mae, m24$mae),
                          original_rmse = c(o1$rmse, o24$rmse), optimized_rmse = c(m1$rmse, m24$rmse),
                          original_r2 = c(o1$r2, o24$r2), optimized_r2 = c(m1$r2, m24$r2)),
               file.path(METRICS, "final_optimization_comparison.csv"))
write_json_file(list(`1h_model` = "XGBoost-1H", `24h_model` = "XGBoost-24H-Direct", ensemble_weights = list(xgb = 1),
                     log_transform = TRUE, p90_threshold = p90, features = as.list(feat_cols)),
                file.path(METRICS, "final_selected_model.json"))

writeLines(c(
  "# Final Advanced Forecasting Optimization", "",
  "## 1. Baseline performance (untuned XGBoost, Module 7)",
  sprintf("- 1-H: MAE=%.4f, RMSE=%.4f, R2=%.4f", o1$mae, o1$rmse, o1$r2),
  sprintf("- 24-H: MAE=%.4f, RMSE=%.4f, R2=%.4f", o24$mae, o24$rmse, o24$r2), "",
  "## 2. Features", sprintf("- %d features: calendar/cyclical, lags up to 168 h, rolling stats, EWMA (spans 3-48), same-hour averages, previous-day profile.", length(feat_cols)), "",
  "## 3. XGBoost tuning",
  "- 3-config search for 1-H and 2-config search for 24-H, chosen on validation MAE with early stopping.",
  sprintf("- Best 1-H validation MAE: %.4f; best 24-H: %.4f", best_1h$val_mae, best_24h$val_mae),
  "- The target is log1p-transformed; all metrics are reported on the original kWh scale.", "",
  "## 4. Deep learning", "LSTM/GRU are not part of the R port: the Python project's final ensemble gave them weight 0, so XGBoost alone is the production model.", "",
  "## 5. Final 1-H test results",
  sprintf("- **XGBoost-1H:** MAE=%.4f, RMSE=%.4f, R2=%.4f", m1$mae, m1$rmse, m1$r2), "",
  "## 6. Final 24-H test results",
  sprintf("- XGBoost-24H (direct): MAE=%.4f, RMSE=%.4f, R2=%.4f", m24$mae, m24$rmse, m24$r2), "",
  "## 7. Leakage controls",
  "- Every rolling/EWMA feature excludes the current target (series shifted by one hour).",
  "- Same-hour history uses only past lags.", "- The test set was evaluated exactly once, after all decisions were frozen.", "",
  "## 8. Accuracy within tolerance",
  vapply(c(10, 20, 30, 50), function(t) sprintf("- +/-%d%%: %.2f%%", t, m1[[paste0("acc_", t)]]), ""), "",
  "## 9. Limitations",
  "- Household consumption is highly stochastic; R2 above 0.9 is not achievable without leakage.",
  "- Accuracy within +/-10% is limited by inherent minute-to-hour variance."),
  file.path(DOCS, "final_forecasting_optimization.md"))

cat(sprintf("\nXGBoost-1H : MAE=%.4f RMSE=%.4f R2=%.4f (baseline MAE %.4f)\n", m1$mae, m1$rmse, m1$r2, o1$mae))
cat(sprintf("XGBoost-24H: MAE=%.4f RMSE=%.4f R2=%.4f\n", m24$mae, m24$rmse, m24$r2))
cat(sprintf("Peak demand (1H): precision=%.3f recall=%.3f f1=%.3f\n", pk$precision, pk$recall, pk$f1_score))
cat("Models saved to models/final/\n")
