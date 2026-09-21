# Forecasting models, splits and evaluation metrics.
# Ports of src/forecasting.py, src/model_evaluation.py and the helpers in
# scripts/final_advanced_optimization.py. LSTM/GRU are intentionally not ported: the final
# ensemble gave them weight 0, so XGBoost alone is the production model.

# --- split ---------------------------------------------------------------------
chronological_split <- function(df, train_ratio = 0.7, val_ratio = 0.15) {
  df <- df[order(df$timestamp), ]
  n <- nrow(df)
  train_end <- floor(n * train_ratio)
  val_end <- train_end + floor(n * val_ratio)
  list(train = df[seq_len(train_end), ], val = df[(train_end + 1):val_end, ], test = df[(val_end + 1):n, ])
}

# --- metrics -------------------------------------------------------------------
mae <- function(a, p) mean(abs(a - p))
rmse <- function(a, p) sqrt(mean((a - p)^2))
r2_score <- function(a, p) 1 - sum((a - p)^2) / sum((a - mean(a))^2)

mape_pct <- function(a, p, eps = 1e-8) {
  keep <- a > eps
  if (!any(keep)) return(NA_real_)
  mean(abs((a[keep] - p[keep]) / a[keep])) * 100
}

# Symmetric MAPE, bounded to [0, 200] %.
smape_pct <- function(a, p, eps = 1e-4) {
  denom <- abs(a) + abs(p)
  keep <- denom > eps
  if (!any(keep)) return(NA_real_)
  mean(2 * abs(a[keep] - p[keep]) / denom[keep]) * 100
}

# % of predictions within +/- `tol` (relative) of the actual value.
acc_within <- function(a, p, tol, eps = 1e-4) mean(abs(a - p) / pmax(abs(a), eps) <= tol) * 100

regression_metrics <- function(actual, predicted) {
  list(mae = mae(actual, predicted), rmse = rmse(actual, predicted), mape = mape_pct(actual, predicted),
       r2 = r2_score(actual, predicted), prediction_count = length(actual))
}

full_metrics <- function(actual, predicted, label = "") {
  out <- list(model = label, mae = mae(actual, predicted), rmse = rmse(actual, predicted),
              mape = mape_pct(actual, predicted, 1e-4), smape = smape_pct(actual, predicted),
              r2 = r2_score(actual, predicted))
  for (tol in c(10, 15, 20, 25, 30, 40, 50)) out[[paste0("acc_", tol)]] <- acc_within(actual, predicted, tol / 100)
  out$n <- length(actual)
  out
}

# Classification metrics for "peak" hours (value > threshold).
peak_metrics <- function(actual, predicted, threshold) {
  a <- actual > threshold
  p <- predicted > threshold
  tp <- sum(a & p)
  fp <- sum(!a & p)
  fn <- sum(a & !p)
  precision <- if (tp + fp > 0) tp / (tp + fp) else 0
  recall <- if (tp + fn > 0) tp / (tp + fn) else 0
  f1 <- if (precision + recall > 0) 2 * precision * recall / (precision + recall) else 0
  list(precision = precision, recall = recall, f1_score = f1,
       true_positives = tp, false_positives = fp, false_negatives = fn)
}

improvement_pct <- function(baseline, model, lower_is_better = TRUE) {
  if (is.na(baseline) || baseline == 0) return(0)
  if (lower_is_better) (baseline - model) / baseline * 100 else (model - baseline) / baseline * 100
}

# --- XGBoost -------------------------------------------------------------------
# Trains on log1p(kWh) with early stopping on the validation set; `params` uses the
# scikit-learn style names the original grid used.
train_xgb <- function(X_tr, y_tr, X_val, y_val, params, log_transform = TRUE, nrounds = 2000, early_stopping = 50) {
  tf <- if (log_transform) log1p else identity
  dtrain <- xgboost::xgb.DMatrix(as.matrix(X_tr), label = tf(y_tr))
  dval <- xgboost::xgb.DMatrix(as.matrix(X_val), label = tf(y_val))
  full <- c(list(objective = "reg:squarederror", tree_method = "hist", seed = 42, nthread = parallel::detectCores()),
            params)
  model <- xgboost::xgb.train(full, dtrain, nrounds = nrounds, evals = list(val = dval),
                              early_stopping_rounds = early_stopping, verbose = 0)
  list(model = model, val_mae = mae(y_val, xgb_predict(model, X_val, log_transform)))
}

xgb_predict <- function(model, X, log_transform = TRUE) {
  p <- as.numeric(predict(model, as.matrix(X)))
  if (log_transform) expm1(p) else p
}

# --- basic-feature next-hour vector (used by the recursive 24h forecasts) -----------
# Mirrors the Spark feature table of spark_basic_features() for one future hour.
basic_next_features <- function(history, next_ts, p90, feature_cols) {
  hour <- hour_of(next_ts)
  dow <- lubridate::wday(next_ts, week_start = 1) - 1L
  month <- lubridate::month(next_ts)
  f <- c(year = lubridate::year(next_ts), month = month, day = lubridate::day(next_ts),
         day_of_month = lubridate::day(next_ts), day_of_week = dow, hour = hour,
         week_of_year = lubridate::isoweek(next_ts), quarter = lubridate::quarter(next_ts),
         is_weekend = as.integer(dow >= 5),
         hour_sin = sin(2 * pi * hour / 24), hour_cos = cos(2 * pi * hour / 24),
         dow_sin = sin(2 * pi * dow / 7), dow_cos = cos(2 * pi * dow / 7),
         month_sin = sin(2 * pi * month / 12), month_cos = cos(2 * pi * month / 12))
  n <- length(history)
  at <- function(k) if (n >= k) history[n - k + 1] else NA_real_
  f <- c(f, setNames(vapply(BASIC_LAGS, at, numeric(1)), paste0("lag_", BASIC_LAGS)))
  for (w in BASIC_ROLLING) {
    win <- if (n >= w) tail(history, w) else NA_real_
    f[paste0("rolling_mean_", w)] <- mean(win)
    if (w == 24) {
      f["rolling_std_24"] <- sd(win)
      f["rolling_min_24"] <- min(win)
      f["rolling_max_24"] <- max(win)
    }
  }
  f["trend_3h"] <- at(1) - at(3)
  f["trend_24h"] <- at(1) - at(24)
  f["is_high_demand_previous_hour"] <- as.integer(at(1) >= p90)
  f[feature_cols]
}

# Recursive multi-step forecast: each prediction is fed back as the newest "observation".
# `predict_fn` takes a one-row data.frame of features and returns a number.
predict_recursive <- function(predict_fn, history, start_ts, p90, feature_cols, steps = 24) {
  preds <- numeric(steps)
  for (i in seq_len(steps)) {
    row <- basic_next_features(history, start_ts + 3600 * (i - 1), p90, feature_cols)
    preds[i] <- predict_fn(as.data.frame(as.list(row)))
    history <- c(history, preds[i])
  }
  data.frame(timestamp = start_ts + 3600 * (seq_len(steps) - 1), actual = NA_real_, predicted = preds,
             horizon = seq_len(steps))
}

# --- SARIMA --------------------------------------------------------------------
SARIMA_ORDER <- c(1, 0, 0)
SARIMA_SEASONAL <- list(order = c(1, 0, 0), period = 24)

# Household demand has a non-zero mean while the model has no intercept (as in the original
# statsmodels setup), so the seasonal AR term ends up near a unit root and the maximum-likelihood
# step can fail to converge. Fall back to the conditional-sum-of-squares fit in that case.
fit_sarima <- function(series) {
  x <- ts(series, frequency = 24)
  fit <- function(method) stats::arima(x, order = SARIMA_ORDER, seasonal = SARIMA_SEASONAL,
                                       include.mean = FALSE, method = method)
  tryCatch(fit("CSS-ML"), error = function(e) fit("CSS"))
}

# One-step-ahead predictions over `series` with the fitted parameters held fixed.
sarima_one_step <- function(fit, series) {
  refit <- stats::arima(ts(series, frequency = 24), order = SARIMA_ORDER, seasonal = SARIMA_SEASONAL,
                        include.mean = FALSE, fixed = stats::coef(fit), transform.pars = FALSE)
  as.numeric(series) - as.numeric(stats::residuals(refit))
}

# --- misc ----------------------------------------------------------------------
# pandas-style forward fill, then zeros for anything still missing.
locf_zero <- function(df) {
  for (nm in setdiff(names(df), "timestamp")) {
    df[[nm]] <- data.table::nafill(as.numeric(df[[nm]]), type = "locf")
    df[[nm]][is.na(df[[nm]])] <- 0
  }
  df
}
