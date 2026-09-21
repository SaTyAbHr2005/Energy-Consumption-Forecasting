# Checks for the data + ML pipeline. Needs Java + Spark (use the pipeline Docker image). From the project root:
#   Rscript backend/tests/run_pipeline_checks.R
source("backend/pipeline/R/common.R")
source("backend/pipeline/R/spark_stages.R")
source("backend/pipeline/R/models.R")

check <- function(name, ok) {
  cat(sprintf("%s  %s\n", if (isTRUE(ok)) "PASS" else "FAIL", name))
  if (!isTRUE(ok)) quit(status = 1)
}
near <- function(a, b, tol = 1e-8) isTRUE(all.equal(as.numeric(a), as.numeric(b), tolerance = tol))

# --- metrics -------------------------------------------------------------------------
a <- c(1, 2, 3, 4)
p <- c(1, 3, 3, 2)
check("mae", near(mae(a, p), 0.75))
check("rmse", near(rmse(a, p), sqrt(5 / 4)))
check("r2 of a perfect forecast is 1", near(r2_score(a, a), 1))
check("r2 of the mean forecast is 0", near(r2_score(a, rep(mean(a), 4)), 0))
check("mape ignores zero actuals", near(mape_pct(c(0, 2), c(5, 1)), 50))
check("accuracy within tolerance", near(acc_within(c(10, 10, 10, 10), c(10.5, 11.5, 9, 20), 0.10), 50))
pm <- peak_metrics(c(1, 3, 3, 0), c(3, 3, 0, 0), threshold = 2)
check("peak metrics count tp/fp/fn", pm$true_positives == 1 && pm$false_positives == 1 && pm$false_negatives == 1)
check("peak precision/recall/f1", near(pm$precision, 0.5) && near(pm$recall, 0.5) && near(pm$f1_score, 0.5))
check("improvement over baseline", near(improvement_pct(10, 8), 20) && improvement_pct(0, 1) == 0)

sp <- chronological_split(data.frame(timestamp = as.POSIXct("2026-01-01", tz = "UTC") + 3600 * 0:99, x = 1:100))
check("70/15/15 chronological split", nrow(sp$train) == 70 && nrow(sp$val) == 15 && nrow(sp$test) == 15 &&
        max(sp$train$timestamp) < min(sp$val$timestamp) && max(sp$val$timestamp) < min(sp$test$timestamp))

# --- smart-grid helpers used by the pipeline ---------------------------------------------
costs <- calculate_tou_cost(data.frame(timestamp = as.POSIXct("2026-01-01", tz = "UTC") + 3600 * c(3, 10, 18), predicted = c(1, 1, 1)))
sm <- tou_summary(costs)
check("TOU summary splits energy and cost by period",
      near(sm$off_peak_cost_inr, 3) && near(sm$normal_cost_inr, 6) && near(sm$peak_cost_inr, 10) && near(sm$total_simulated_cost_inr, 19))
day <- data.frame(timestamp = as.POSIXct("2026-01-01", tz = "UTC") + 3600 * 0:23, predicted = rep(1, 24))
day$predicted[19] <- 3
shifts <- recommend_load_shifts(day, threshold = 2)
daily <- daily_savings_analysis(calculate_tou_cost(day)[c("timestamp", "consumption_kwh")], shifts)
check("daily savings = baseline - optimised", nrow(daily) == 1 && near(daily$baseline_cost - daily$optimized_simulated_cost, daily$estimated_savings) &&
        daily$estimated_savings > 0)

# --- XGBoost save/load round trip (the API loads what the pipeline saves) --------------------
set.seed(1)
X <- matrix(rnorm(600), ncol = 3, dimnames = list(NULL, c("a", "b", "c")))
y <- exp(X[, 1] / 2) + 0.1 * X[, 2]^2
fit <- train_xgb(X[1:150, ], y[1:150], X[151:200, ], y[151:200], list(eta = 0.1, max_depth = 3), nrounds = 200)
f <- tempfile(fileext = ".json")
xgboost::xgb.save(fit$model, f)
check("saved XGBoost model reloads with identical predictions",
      near(xgb_predict(fit$model, X[151:200, ]), xgb_predict(xgboost::xgb.load(f), X[151:200, ]), 1e-6))
check("XGBoost learns the signal (validation MAE < baseline)", fit$val_mae < mae(y[151:200], rep(mean(y[1:150]), 50)))

# --- SARIMA -----------------------------------------------------------------------------------------
set.seed(2)
hours <- 0:(24 * 20 - 1)
series <- 1 + sin(2 * pi * hours / 24) + rnorm(length(hours), sd = 0.05)
fit <- fit_sarima(series[1:336])
one_step <- sarima_one_step(fit, series[337:480])
check("SARIMA gives one finite one-step prediction per observation", length(one_step) == 144 && all(is.finite(one_step)))
check("SARIMA 24h forecast has 24 values", length(predict(fit, n.ahead = 24)$pred) == 24)

# --- Spark stages on a small synthetic series -----------------------------------------------------------
sc <- spark_session("PipelineChecks")
tryCatch({
  n <- 500
  ts <- as.POSIXct("2026-01-01 00:00:00", tz = "UTC") + 3600 * (seq_len(n) - 1)
  hourly <- data.frame(timestamp = ts, energy_kwh = 1 + 0.5 * sin(2 * pi * seq_len(n) / 24) + (seq_len(n) %% 7) / 10,
                       avg_voltage = 240 + (seq_len(n) %% 5), total_sub_metering_1 = 1)
  hourly$energy_kwh[100:101] <- NA               # 2-hour gap: interpolated
  hourly$energy_kwh[200:205] <- NA               # 6-hour gap: left missing
  hourly$energy_kwh[300] <- 50                   # outlier
  hourly <- hourly[-400, ]                       # a missing hour: must reappear in the continuous index

  res <- preprocess_hourly(sc, hourly)
  clean <- res$clean
  check("continuous hourly index restored", nrow(clean) == n && res$report$missing_hourly_records == 1)
  check("short gap is interpolated between neighbours", !anyNA(clean$energy_kwh[100:101]) &&
          near(clean$energy_kwh[100], (hourly$energy_kwh[99] + hourly$energy_kwh[102]) / 2))
  check("long gap is left missing and flagged", all(is.na(clean$energy_kwh[200:205])) && sum(clean$is_long_gap) == 6)
  check("outlier is flagged by the IQR rule", clean$is_energy_outlier[300] == 1)
  check("report counts missing values before/after", res$report$missing_values_before$energy_kwh == 9 &&
          res$report$missing_values_after$energy_kwh == 6) # 2 + 1 short gaps filled, the 6-hour gap stays

  # Train/serve consistency: the Spark feature table and the R next-hour builder must agree.
  full <- res$clean # fill every null so the feature stage's "drop rows with any null" keeps all rows
  full[] <- lapply(full, function(x) if (is.numeric(x)) ifelse(is.na(x), 1, x) else x)
  features <- spark_basic_features(sc, full)$features
  check("burn-in of 168 hours is dropped", nrow(features) == n - 168 && min(features$timestamp) == ts[169])
  feature_cols <- setdiff(names(features), c("timestamp", "energy_kwh", "avg_voltage", "total_sub_metering_1",
                                              "is_long_gap", "is_energy_outlier"))
  p90 <- quantile(full$energy_kwh, 0.9, names = FALSE)
  worst <- 0
  for (k in c(200, 350, 480)) {
    mine <- basic_next_features(full$energy_kwh[seq_len(k - 1)], full$timestamp[k], p90, feature_cols)
    theirs <- unlist(features[features$timestamp == full$timestamp[k], feature_cols])
    worst <- max(worst, max(abs(mine - theirs)))
  }
  check(sprintf("Spark feature table == R next-hour features (max diff %.2e)", worst), worst < 1e-3)
}, finally = sparklyr::spark_disconnect(sc))

cat("\nAll pipeline checks passed.\n")
