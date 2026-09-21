# Stage 6: baseline forecasting models on the chronological 70/15/15 split.
# Naive, SARIMA, Random Forest and XGBoost; each yields 1-hour predictions for the whole test set
# plus a 24-hour forecast for its last 24 hours. Writes results/predictions/*_predictions.parquet.
source("backend/pipeline/R/common.R")
source("backend/pipeline/R/spark_stages.R") # BASIC_LAGS / BASIC_ROLLING
source("backend/pipeline/R/models.R")

banner("Forecasting models training pipeline")
df <- read_parquet_file(FEATURES_FILE)
stopifnot("chronological ordering failed" = !is.unsorted(df$timestamp),
          "missing values in feature dataset" = !anyNA(df))

sp <- chronological_split(df)
train <- sp$train; val <- sp$val; test <- sp$test
n_test <- nrow(test)
cat(sprintf("Records: %d total, %d train, %d validation, %d test\n", nrow(df), nrow(train), nrow(val), n_test))

ts_range <- function(d) list(fmt_ts(min(d$timestamp)), fmt_ts(max(d$timestamp)))
write_json_file(list(
  total_records = nrow(df), train_records = nrow(train), validation_records = nrow(val), test_records = n_test,
  train_start = fmt_ts(min(train$timestamp)), train_end = fmt_ts(max(train$timestamp)),
  validation_start = fmt_ts(min(val$timestamp)), validation_end = fmt_ts(max(val$timestamp)),
  test_start = fmt_ts(min(test$timestamp)), test_end = fmt_ts(max(test$timestamp))),
  file.path(METRICS, "data_split.json"))

excluded <- c("timestamp", "energy_kwh", "avg_global_active_power", "avg_global_reactive_power", "avg_voltage",
              "avg_global_intensity", "total_sub_metering_1", "total_sub_metering_2", "total_sub_metering_3",
              "is_long_gap", "is_energy_outlier")
feature_cols <- setdiff(names(df), excluded)
p90 <- quantile(df$energy_kwh, 0.90, names = FALSE)
write_json_file(list(features = feature_cols), file.path(METRICS, "model_features.json"))

save_preds <- function(frames, name) {
  out <- do.call(rbind, frames)
  write_parquet_file(out, file.path(PREDICTIONS, paste0(name, "_predictions.parquet")))
  invisible(out)
}
pred_frame <- function(d, predicted, horizon, model) {
  data.frame(timestamp = d$timestamp, actual = d$energy_kwh, predicted = predicted, horizon = horizon, model = model)
}
last24 <- function(frame, model) { # 24-hour recursive forecast over the last 24 hours of the test set
  frame$actual <- tail(test$energy_kwh, 24)
  frame$horizon <- 24L
  frame$model <- model
  frame
}
history <- head(test$energy_kwh, n_test - 24)
start_24 <- test$timestamp[n_test - 23]

# --- 1. naive baselines -------------------------------------------------------
cat("\n[1/4] Naive baselines\n")
save_preds(list(pred_frame(test, test$lag_1, 1L, "Naive_1h"), pred_frame(test, test$lag_24, 24L, "Naive_24h")), "naive")

# --- 2. SARIMA(1,0,0)(1,0,0)[24], fitted on the last two weeks of training data ------
cat("[2/4] SARIMA\n")
fit <- fit_sarima(tail(train$energy_kwh, 336))
sarima_1h <- pred_frame(test, sarima_one_step(fit, test$energy_kwh), 1L, "SARIMA")
sarima_24h <- data.frame(timestamp = tail(test$timestamp, 24), actual = tail(test$energy_kwh, 24),
                         predicted = as.numeric(predict(fit, n.ahead = 24)$pred), horizon = 24L, model = "SARIMA_24h")
save_preds(list(sarima_1h, sarima_24h), "sarima")

# --- 3. Random forest -----------------------------------------------------------
cat("[3/4] Random forest\n")
rf <- ranger::ranger(x = train[feature_cols], y = train$energy_kwh, num.trees = 50, seed = 42,
                     num.threads = parallel::detectCores())
rf_predict <- function(x) as.numeric(predict(rf, data = x)$predictions)
rf_24h <- last24(predict_recursive(function(row) rf_predict(row), history, start_24, p90, feature_cols)[c("timestamp", "actual", "predicted")], "RandomForest")
save_preds(list(pred_frame(test, rf_predict(test[feature_cols]), 1L, "RandomForest"), rf_24h), "random_forest")

# --- 4. XGBoost (untuned baseline) --------------------------------------------------
cat("[4/4] XGBoost\n")
xgb <- xgboost::xgb.train(list(objective = "reg:squarederror", eta = 0.1, seed = 42, nthread = parallel::detectCores()),
                          xgboost::xgb.DMatrix(as.matrix(train[feature_cols]), label = train$energy_kwh), nrounds = 100, verbose = 0)
xgb_predict_row <- function(x) as.numeric(predict(xgb, as.matrix(x[feature_cols])))
xgb_24h <- last24(predict_recursive(xgb_predict_row, history, start_24, p90, feature_cols)[c("timestamp", "actual", "predicted")], "XGBoost")
xgb_all <- save_preds(list(pred_frame(test, xgb_predict_row(test), 1L, "XGBoost"), xgb_24h), "xgboost")

# The API serves this file (parquet would need the heavy arrow package at runtime).
write_csv_file(data.frame(timestamp = fmt_ts(xgb_all$timestamp, "T"), horizon = xgb_all$horizon, predicted = xgb_all$predicted),
               file.path(PREDICTIONS, "xgboost_predictions.csv"))

write_json_file(list(
  models = list("Naive", "SARIMA", "RandomForest", "XGBoost"), training_records = nrow(train),
  validation_records = nrow(val), test_records = n_test,
  training_start = fmt_ts(min(train$timestamp)), training_end = fmt_ts(max(train$timestamp)),
  validation_start = fmt_ts(min(val$timestamp)), validation_end = fmt_ts(max(val$timestamp)),
  test_start = fmt_ts(min(test$timestamp)), test_end = fmt_ts(max(test$timestamp)),
  forecast_horizons = list(1, 24), training_status = "SUCCESS",
  sarima_config = list(order = list(1, 0, 0), seasonal_order = list(1, 0, 0, 24)),
  note = "LSTM/GRU were dropped in the R port: they received weight 0 in the final ensemble."),
  file.path(METRICS, "training_summary.json"))
cat("\nBaseline models trained; predictions saved to results/predictions/\n")
