# Stage 7: evaluate every baseline model on the unseen test set and pick the best one.
source("backend/pipeline/R/common.R")
source("backend/pipeline/R/models.R")
library(ggplot2)

banner("Model evaluation and selection")
p90 <- read_json_file(file.path(METRICS, "eda_summary.json"))$peak_demand_analysis$percentile_90_threshold

files <- list.files(PREDICTIONS, pattern = "_predictions\\.parquet$", full.names = TRUE)
metrics <- list()
peaks <- list()
kept <- list()
for (f in files) {
  d <- read_parquet_file(f)
  for (key in unique(paste(d$model, d$horizon))) {
    g <- d[paste(d$model, d$horizon) == key, ]
    g <- g[!is.na(g$actual) & !is.na(g$predicted), ]
    if (nrow(g) == 0) next
    base <- strsplit(g$model[1], "_")[[1]][1] # "Naive" from "Naive_1h"
    h <- g$horizon[1]
    kept[[paste(base, h)]] <- g
    metrics[[length(metrics) + 1]] <- c(list(model = base, horizon = h), regression_metrics(g$actual, g$predicted))
    peaks[[length(peaks) + 1]] <- c(list(model = base, horizon = h), peak_metrics(g$actual, g$predicted, p90))
  }
}
df_metrics <- do.call(rbind, lapply(metrics, as.data.frame))
df_peaks <- do.call(rbind, lapply(peaks, as.data.frame))
df_metrics <- df_metrics[order(df_metrics$model, df_metrics$horizon), ]
df_peaks <- df_peaks[order(df_peaks$model, df_peaks$horizon), ]

# improvement over the naive baseline (same horizon)
for (col in c("mae", "rmse", "mape")) df_metrics[[paste0(col, "_improvement_vs_naive")]] <- 0
for (h in c(1, 24)) {
  naive <- df_metrics[df_metrics$model == "Naive" & df_metrics$horizon == h, ]
  if (nrow(naive) == 0) next
  rows <- which(df_metrics$horizon == h)
  for (col in c("mae", "rmse", "mape")) {
    df_metrics[[paste0(col, "_improvement_vs_naive")]][rows] <- vapply(df_metrics[[col]][rows], function(v) improvement_pct(naive[[col]], v), 0)
  }
}
write_csv_file(df_metrics, file.path(METRICS, "model_comparison.csv"))
write_csv_file(df_peaks, file.path(METRICS, "peak_evaluation.csv"))

h24 <- df_metrics[df_metrics$horizon == 24, ]
h1 <- df_metrics[df_metrics$horizon == 1, ]
best_24 <- if (nrow(h24)) h24$model[which.min(h24$rmse)] else NA
best_1 <- if (nrow(h1)) h1$model[which.min(h1$rmse)] else NA
best <- if (!is.na(best_24)) best_24 else best_1
beats_naive <- h24$mae_improvement_vs_naive[h24$model == best] > 0
selection <- list(selected_model = best, selection_basis = "Lowest RMSE on the 24-hour forecasting horizon.",
                  primary_metric = "RMSE", best_horizon_1_model = best_1, best_horizon_24_model = best_24,
                  beats_naive = isTRUE(beats_naive))
write_json_file(selection, file.path(METRICS, "selected_model.json"))

# --- figures ---------------------------------------------------------------------
metric_plot <- function(metric, title, file) {
  save_plot(ggplot(df_metrics, aes(model, .data[[metric]], fill = factor(horizon))) + geom_col(position = "dodge") +
              labs(title = title, y = toupper(metric), fill = "Horizon") + theme_energy(), file)
}
metric_plot("mae", "Model Comparison: MAE by Horizon", "model_mae_comparison.png")
metric_plot("rmse", "Model Comparison: RMSE by Horizon", "model_rmse_comparison.png")
metric_plot("mape", "Model Comparison: MAPE by Horizon", "model_mape_comparison.png")
metric_plot("r2", "Model Comparison: R2 by Horizon", "model_r2_comparison.png")

best_df <- kept[[paste(best, 24)]]
if (!is.null(best_df)) {
  best_df <- best_df[order(best_df$timestamp), ]
  window <- head(best_df, 336)
  long <- rbind(data.frame(timestamp = window$timestamp, kind = "Actual", kwh = window$actual),
                data.frame(timestamp = window$timestamp, kind = "Predicted", kwh = window$predicted))
  save_plot(ggplot(long, aes(timestamp, kwh, color = kind)) + geom_line(alpha = 0.7) +
              scale_color_manual(values = c(Actual = "blue", Predicted = "red")) +
              labs(title = sprintf("Actual vs Predicted - %s (Horizon 24)", best), x = "Date", y = "Energy (kWh)", color = NULL) +
              theme_energy(), "actual_vs_predicted.png", width = 15)
  best_df$error <- best_df$actual - best_df$predicted
  save_plot(ggplot(best_df, aes(error)) + geom_histogram(bins = 50, fill = "steelblue") +
              labs(title = sprintf("Residual Distribution - %s (Horizon 24)", best), x = "Error (Actual - Predicted)") + theme_energy(),
            "residual_distribution.png")
  best_df$hour <- hour_of(best_df$timestamp)
  by_hour <- aggregate(error ~ hour, best_df, function(e) c(MAE = mean(abs(e)), RMSE = sqrt(mean(e^2))))
  by_hour <- data.frame(hour = by_hour$hour, MAE = by_hour$error[, "MAE"], RMSE = by_hour$error[, "RMSE"])
  save_plot(ggplot(rbind(data.frame(hour = by_hour$hour, metric = "MAE", v = by_hour$MAE),
                         data.frame(hour = by_hour$hour, metric = "RMSE", v = by_hour$RMSE)), aes(factor(hour), v, fill = metric)) +
              geom_col(position = "dodge") + labs(title = sprintf("Error by Hour of Day - %s (Horizon 24)", best),
                                                  x = "Hour of Day", y = "Error", fill = NULL) + theme_energy(), "error_by_hour.png")
}

# --- documentation -----------------------------------------------------------------
fmt_table <- function(d) paste(utils::capture.output(print(d, row.names = FALSE, digits = 4)), collapse = "\n")
writeLines(c(
  "# Module 8: Model Evaluation & Selection", "",
  "## 1. Purpose",
  "Objectively evaluate every baseline forecasting model on a completely unseen test set and choose the best one for smart-grid decision support.", "",
  "## 2. Evaluation Dataset",
  sprintf("Strict chronological test set; the 24-hour horizon is scored on its last %d hours. The test data was never used for training, tuning or scaling.",
          max(h24$prediction_count)), "",
  "## 3. Models Evaluated",
  "- **Naive baseline**: previous hour (1h) / same hour previous day (24h).",
  "- **SARIMA(1,0,0)(1,0,0)[24]**: statistical seasonal model, fitted on the last two weeks of training data.",
  "- **Random Forest** (ranger, 50 trees) and **XGBoost**: tree models on the calendar/lag/rolling features.",
  "- LSTM/GRU were dropped in the R port: in the earlier Python project they received weight 0 in the final ensemble.", "",
  "## 4. Metrics", "MAE, RMSE, MAPE and R2.", "",
  "## 5. Horizons", "- **Horizon 1**: next hour.", "- **Horizon 24**: recursive 24-hour forecast.", "",
  "## 6. Baseline comparison", "A positive improvement % means the model beat the Naive baseline.", "",
  "## 7. Peak-demand evaluation",
  sprintf("Ability to flag hours above the 90th percentile threshold (%.2f kWh).", p90), "",
  "## 8. Selected model",
  sprintf("- **Best model:** `%s`", best), sprintf("- **Rationale:** %s", selection$selection_basis),
  sprintf("- **Beats naive baseline:** %s", if (isTRUE(beats_naive)) "YES" else "NO"), "",
  "## 9. Results", "", "### Horizon 24", "```text",
  fmt_table(h24[c("model", "mae", "rmse", "r2", "mae_improvement_vs_naive")]), "```", "",
  "### Peak demand (Horizon 24)", "```text",
  fmt_table(df_peaks[df_peaks$horizon == 24, c("model", "precision", "recall", "f1_score")]), "```"),
  file.path(DOCS, "model_evaluation.md"))

cat("Models evaluated:", paste(unique(df_metrics$model), collapse = ", "), "\n")
cat("Best horizon-1 model:", best_1, "| best horizon-24 model:", best_24, "| selected:", best, "\n")
print(df_metrics[c("model", "horizon", "mae", "rmse", "r2")], row.names = FALSE, digits = 4)
