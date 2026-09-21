# Stage 9: forecast-based smart-grid decision support: peak demand, illustrative time-of-use
# cost, load shifting, savings scenarios and recommendations. Reads the baseline XGBoost
# test-set predictions; the tariff and shifting rules are simulations, not real tariffs.
source("backend/pipeline/R/common.R")
library(ggplot2)

banner("Module 9: smart-grid insights")
historical <- read_parquet_file(CLEAN_FILE)
pred <- read_parquet_file(file.path(PREDICTIONS, "xgboost_predictions.parquet"))
predictions <- pred[pred$horizon == 1, c("timestamp", "predicted")] # the 1-hour test-set forecast schedule

selected_path <- file.path(METRICS, "final_selected_model.json")
threshold <- if (file.exists(selected_path)) read_json_file(selected_path)$p90_threshold else quantile(historical$energy_kwh, 0.90, na.rm = TRUE, names = FALSE)
critical <- quantile(historical$energy_kwh, 0.99, na.rm = TRUE, names = FALSE)

csv_ts <- function(df) { # pandas-style timestamp text
  for (nm in names(df)) if (inherits(df[[nm]], "POSIXct")) df[[nm]] <- fmt_ts(df[[nm]])
  df
}

forecast <- build_peak_demand_forecast(predictions, threshold, critical)
write_csv_file(csv_ts(forecast), file.path(METRICS, "peak_demand_forecast.csv"))

insights <- energy_insights(historical, threshold)
write_json_file(insights, file.path(METRICS, "energy_insights.json"))

costs <- calculate_tou_cost(forecast, "predicted_consumption")
write_csv_file(csv_ts(costs), file.path(METRICS, "tou_cost_analysis.csv"))
write_json_file(c(list(tariff_label = "Illustrative TOU tariff used for simulation.",
                       off_peak_rate = TOU$off_peak_rate, normal_rate = TOU$normal_rate, peak_rate = TOU$peak_rate),
                  tou_summary(costs)), file.path(METRICS, "tou_summary.json"))

shifts <- recommend_load_shifts(predictions, threshold, 0.20)
write_csv_file(csv_ts(shifts), file.path(METRICS, "load_shift_recommendations.csv"))
daily <- daily_savings_analysis(costs[c("timestamp", "consumption_kwh")], shifts)
write_csv_file(daily, file.path(METRICS, "daily_savings_analysis.csv"))

baseline <- sum(costs$simulated_cost_inr)
scenarios <- do.call(rbind, lapply(c(0.10, 0.20, 0.30), function(fraction) {
  s <- recommend_load_shifts(predictions, threshold, fraction)
  data.frame(shiftable_fraction = fraction, energy_shifted_kwh = sum(s$shiftable_energy_kwh),
             simulated_savings_inr = sum(s$estimated_savings),
             savings_percentage = if (baseline > 0) sum(s$estimated_savings) / baseline * 100 else 0)
}))
write_csv_file(scenarios, file.path(METRICS, "load_shift_sensitivity.csv"))

recommendations <- generate_recommendations(historical, forecast, insights, threshold)
savings <- sum(shifts$estimated_savings)
peak_at <- which.max(forecast$predicted_consumption)
write_json_file(list(
  data_mode = "Historical forecast simulation",
  historical_average_consumption = insights$average_hourly_consumption,
  forecast_average_consumption = mean(forecast$predicted_consumption),
  peak_threshold = threshold, critical_threshold = critical,
  predicted_peak_count = sum(forecast$is_peak),
  highest_predicted_demand = max(forecast$predicted_consumption),
  highest_predicted_demand_timestamp = fmt_ts(forecast$timestamp[peak_at]),
  tou_baseline_cost = baseline, potential_optimized_cost = baseline - savings,
  potential_savings = savings, potential_savings_percentage = if (baseline > 0) savings / baseline * 100 else 0,
  total_shiftable_energy = sum(shifts$shiftable_energy_kwh), shiftable_fraction_assumption = 0.20,
  recommendations = recommendations),
  file.path(METRICS, "smart_grid_summary.json"))

# --- figures --------------------------------------------------------------------------------
fig <- file.path(FIGURES, "smart_grid")
save_plot(ggplot(forecast, aes(timestamp, predicted_consumption)) + geom_line() +
            geom_hline(yintercept = threshold, color = "red", linetype = "dashed") +
            geom_point(data = forecast[forecast$is_peak, ], color = "red", size = 0.8) +
            labs(title = "Forecasted Demand and Peak Threshold", x = NULL, y = "kWh") + theme_energy(),
          "forecast_peak_demand.png", dir = fig, width = 12, height = 4)
save_plot(ggplot(data.frame(hour = 0:23, rate = tou_rate(0:23)), aes(hour, rate)) + geom_step() +
            labs(title = "Illustrative TOU Pricing Simulation", x = "Hour", y = "Illustrative INR/kWh") + theme_energy(),
          "tou_pricing_simulation.png", dir = fig, height = 4)
optimized <- if (nrow(daily) > 0) sum(daily$optimized_simulated_cost) else baseline
save_plot(ggplot(data.frame(k = c("Baseline simulated", "Potential optimized"), v = c(baseline, optimized)), aes(k, v)) +
            geom_col(fill = c("#6baed6", "#2171b5")) + labs(title = "Baseline vs Optimized Simulated Cost", x = NULL, y = "INR") + theme_energy(),
          "cost_savings_comparison.png", dir = fig, width = 6, height = 4)
if (nrow(shifts) > 0) {
  save_plot(ggplot(shifts) + geom_segment(aes(x = source_timestamp, xend = destination_timestamp, y = source_predicted_kwh,
                                                yend = destination_predicted_kwh), alpha = 0.5) +
              labs(title = "Potential Load-Shift Pairs", x = NULL, y = "Predicted kWh") + theme_energy(),
            "load_shift_simulation.png", dir = fig, height = 4)
}
save_plot(ggplot(daily, aes(date, estimated_savings)) + geom_line() + geom_point() +
            labs(title = "Daily Potential Simulated Savings", x = NULL, y = "INR") + theme_energy(),
          "daily_savings.png", dir = fig, height = 4)
sev <- as.data.frame(table(level = factor(forecast$demand_level, c("Normal", "High", "Critical"))))
save_plot(ggplot(sev, aes(level, Freq)) + geom_col(fill = "#2c7fb8") +
            labs(title = "Demand Severity Distribution", x = NULL, y = "Hours") + theme_energy(),
          "demand_severity_distribution.png", dir = fig, width = 6, height = 4)

cat(sprintf("Historical average: %.4f kWh/h | forecast average: %.4f kWh/h | peak threshold: %.4f kWh\n",
            insights$average_hourly_consumption, mean(forecast$predicted_consumption), threshold))
cat(sprintf("Predicted peak hours: %d | max predicted demand: %.4f kWh at %s\n",
            sum(forecast$is_peak), max(forecast$predicted_consumption), fmt_ts(forecast$timestamp[peak_at])))
cat(sprintf("Baseline simulated cost: INR %.2f | potential savings: INR %.2f (%.2f%%)\n", baseline, savings,
            if (baseline > 0) savings / baseline * 100 else 0))
for (r in recommendations) cat(sprintf("- [%s] %s\n", r$priority, r$recommendation))
