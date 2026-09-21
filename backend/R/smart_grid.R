# Forecast-based smart-grid decision support (port of src/smart_grid_insights.py).
# Illustrative time-of-use tariff, used for simulation only (INR/kWh).

TOU <- list(off_peak_rate = 3.0, normal_rate = 6.0, peak_rate = 10.0, peak_start = 17L, peak_end = 22L)

tou_period <- function(hour) {
  ifelse(hour >= TOU$peak_start & hour < TOU$peak_end, "peak",
         ifelse(hour < 6 | hour >= 22, "off_peak", "normal"))
}

tou_rate <- function(hour) {
  period <- tou_period(hour)
  ifelse(period == "peak", TOU$peak_rate, ifelse(period == "off_peak", TOU$off_peak_rate, TOU$normal_rate))
}

# predictions: data.frame(timestamp <POSIXct>, predicted <numeric>)
validate_predictions <- function(data) {
  if (anyNA(data$predicted) || any(data$predicted < 0)) {
    value_error("Predicted consumption must be finite and non-negative")
  }
  data[order(data$timestamp), , drop = FALSE]
}

build_peak_demand_forecast <- function(predictions, threshold, critical = NULL) {
  data <- validate_predictions(predictions)
  if (is.null(critical)) critical <- max(quantile(data$predicted, 0.99, names = FALSE), threshold)
  if (critical < threshold) value_error("Critical threshold must be at least the high threshold")
  data.frame(
    timestamp = data$timestamp,
    predicted_consumption = data$predicted,
    demand_level = ifelse(data$predicted >= critical, "Critical", ifelse(data$predicted >= threshold, "High", "Normal")),
    is_peak = data$predicted >= threshold,
    threshold = as.numeric(threshold)
  )
}

# `value_column` names the kWh column of `data`; the result always calls it consumption_kwh.
calculate_tou_cost <- function(data, value_column = "predicted") {
  hour <- hour_of(data$timestamp)
  rate <- tou_rate(hour)
  kwh <- data[[value_column]]
  data.frame(timestamp = data$timestamp, consumption_kwh = kwh,
             tou_period = tou_period(hour), rate_inr_per_kwh = rate,
             simulated_cost_inr = kwh * rate)
}

# Energy and simulated cost by TOU period.
tou_summary <- function(costs) {
  out <- list()
  for (period in c("off_peak", "normal", "peak")) {
    rows <- costs[costs$tou_period == period, ]
    out[[paste0(period, "_energy_kwh")]] <- sum(rows$consumption_kwh)
    out[[paste0(period, "_cost_inr")]] <- sum(rows$simulated_cost_inr)
  }
  out$total_energy_kwh <- sum(costs$consumption_kwh)
  out$total_simulated_cost_inr <- sum(costs$simulated_cost_inr)
  out
}

# Pair high-demand source hours with cheaper, non-peak destination hours.
recommend_load_shifts <- function(forecast, threshold, shiftable_fraction = 0.20) {
  data <- validate_predictions(forecast)
  data$rate <- tou_rate(hour_of(data$timestamp))
  peaks <- data[data$predicted >= threshold, , drop = FALSE]
  peaks <- peaks[order(-peaks$predicted), , drop = FALSE]
  dest <- data[data$predicted < threshold & tou_period(hour_of(data$timestamp)) != "peak", , drop = FALSE]
  dest <- dest[order(dest$rate, dest$predicted), , drop = FALSE]

  used <- as.numeric(c())
  rows <- list()
  for (i in seq_len(nrow(peaks))) {
    src <- peaks[i, ]
    amount <- min(src$predicted * shiftable_fraction, max(src$predicted - threshold, 0))
    if (amount <= 0) next
    src_rate <- tou_rate(hour_of(src$timestamp))
    ok <- !(as.numeric(dest$timestamp) %in% used) &
      as.numeric(dest$timestamp) != as.numeric(src$timestamp) & dest$rate < src_rate
    if (!any(ok)) next
    d <- dest[which(ok)[1], ]
    amount <- min(amount, d$predicted * shiftable_fraction)
    if (amount <= 0) next
    savings <- amount * src_rate - amount * d$rate
    if (savings <= 0) next
    used <- c(used, as.numeric(d$timestamp))
    rows[[length(rows) + 1]] <- data.frame(
      source_timestamp = src$timestamp, source_predicted_kwh = src$predicted,
      destination_timestamp = d$timestamp, destination_predicted_kwh = d$predicted,
      peak_threshold = threshold, shiftable_energy_kwh = amount,
      peak_rate = src_rate, destination_rate = d$rate,
      estimated_cost_before = amount * src_rate, estimated_cost_after = amount * d$rate,
      estimated_savings = savings
    )
  }
  if (length(rows) == 0) {
    return(data.frame(source_timestamp = as.POSIXct(character(), tz = "UTC"), source_predicted_kwh = numeric(),
                      destination_timestamp = as.POSIXct(character(), tz = "UTC"), destination_predicted_kwh = numeric(),
                      peak_threshold = numeric(), shiftable_energy_kwh = numeric(), peak_rate = numeric(),
                      destination_rate = numeric(), estimated_cost_before = numeric(),
                      estimated_cost_after = numeric(), estimated_savings = numeric()))
  }
  do.call(rbind, rows)
}

# Baseline and potential optimised simulated cost by day.
# baseline: data.frame(timestamp, consumption_kwh); shifts: output of recommend_load_shifts().
daily_savings_analysis <- function(baseline, shifts) {
  costs <- calculate_tou_cost(baseline, "consumption_kwh")
  out_cols <- c("date", "baseline_cost", "optimized_simulated_cost", "estimated_savings",
                "savings_percentage", "energy_shifted")
  if (nrow(costs) == 0) return(setNames(data.frame(matrix(ncol = 6, nrow = 0)), out_cols))
  daily <- aggregate(simulated_cost_inr ~ date, data.frame(date = as.Date(costs$timestamp),
                                                           simulated_cost_inr = costs$simulated_cost_inr), sum)
  names(daily)[2] <- "baseline_cost"
  daily$estimated_savings <- 0
  daily$energy_shifted <- 0
  if (nrow(shifts) > 0) {
    src_date <- as.Date(shifts$source_timestamp)
    sav <- tapply(shifts$estimated_savings, src_date, sum)
    eng <- tapply(shifts$shiftable_energy_kwh, src_date, sum)
    idx <- match(as.character(daily$date), names(sav))
    daily$estimated_savings <- ifelse(is.na(idx), 0, as.numeric(sav)[idx])
    daily$energy_shifted <- ifelse(is.na(idx), 0, as.numeric(eng)[idx])
  }
  daily$optimized_simulated_cost <- daily$baseline_cost - daily$estimated_savings
  daily$savings_percentage <- ifelse(daily$baseline_cost > 0, daily$estimated_savings / daily$baseline_cost * 100, 0)
  daily[out_cols]
}

# Deterministic household statistics from measured history.
energy_insights <- function(history, peak_threshold, top_n = 5) {
  data <- history[!is.na(history$energy_kwh), c("timestamp", "energy_kwh")]
  data <- data[order(data$timestamp), , drop = FALSE]
  hour <- hour_of(data$timestamp)
  dow <- lubridate::wday(data$timestamp, week_start = 1) - 1L
  weekend <- dow >= 5
  hourly <- tapply(data$energy_kwh, hour, mean)
  daily <- tapply(data$energy_kwh, as.Date(data$timestamp), sum)
  top_rows <- function(idx) {
    lapply(idx, function(i) list(timestamp = fmt_ts(data$timestamp[i], "T"), energy_kwh = data$energy_kwh[i]))
  }
  list(
    record_count = nrow(data),
    average_hourly_consumption = mean(data$energy_kwh),
    maximum_hourly_consumption = max(data$energy_kwh),
    minimum_hourly_consumption = min(data$energy_kwh),
    average_daily_consumption = mean(daily),
    weekday_average = mean(data$energy_kwh[!weekend]),
    weekend_average = mean(data$energy_kwh[weekend]),
    highest_consumption_hour = as.integer(names(hourly)[which.max(hourly)]),
    lowest_consumption_hour = as.integer(names(hourly)[which.min(hourly)]),
    peak_demand_frequency = mean(data$energy_kwh >= peak_threshold),
    top_5_highest_consumption_hours = top_rows(head(order(-data$energy_kwh), top_n)),
    top_5_lowest_consumption_hours = top_rows(head(order(data$energy_kwh), top_n))
  )
}

# Rules backed by calculated historical/forecast metrics.
generate_recommendations <- function(history, peak_table, insights, peak_threshold) {
  recs <- list()
  add <- function(recommendation, reason, priority, metric) {
    recs[[length(recs) + 1]] <<- list(recommendation = recommendation, reason = reason,
                                      priority = priority, supporting_metric = metric)
  }
  evening <- peak_table[hour_of(peak_table$timestamp) %in% 17:21, ]
  if (nrow(evening) > 0 && mean(evening$predicted_consumption) >= peak_threshold) {
    add("Shift flexible loads away from the evening peak.",
        "Forecasted evening demand meets or exceeds the high-demand threshold.", "High",
        sprintf("Mean predicted evening demand = %.2f kWh", mean(evening$predicted_consumption)))
  }
  wk <- insights$weekday_average
  we <- insights$weekend_average
  if (!is.nan(we) && !is.nan(wk) && we > wk * 1.10) {
    add("Review appliance usage during high-consumption weekend periods.",
        "Measured weekend consumption is materially higher than weekday consumption.", "Medium",
        sprintf("Weekend average = %.2f vs weekday = %.2f kWh/hour", we, wk))
  }
  n_peaks <- sum(peak_table$is_peak)
  if (n_peaks >= 2) {
    add("Consider shifting flexible loads away from repeated high-demand periods.",
        "Multiple predicted periods exceed the high-demand threshold.", "Medium",
        sprintf("Predicted peak periods = %d", n_peaks))
  }
  if (nrow(history) > 0) {
    overnight <- mean(history$energy_kwh[hour_of(history$timestamp) %in% 0:5], na.rm = TRUE)
    overall <- mean(history$energy_kwh, na.rm = TRUE)
    if (!is.nan(overnight) && overall != 0 && overnight > overall * 1.15) {
      add("Review always-on loads during overnight hours.",
          "Measured overnight consumption is unusually high relative to the household average.", "Low",
          sprintf("Overnight average = %.2f vs overall = %.2f kWh/hour", overnight, overall))
    }
  }
  recs
}

# Turn a completed forecast into the dashboard payload.
smart_grid_analysis <- function(result) {
  if (!identical(result$status, "complete")) return(result)
  history <- result$historical
  forecast <- result$forecast
  fc <- data.frame(timestamp = forecast$timestamp, predicted = forecast$predicted_consumption)
  threshold <- result$peak_threshold
  critical <- quantile(history$energy_kwh, 0.99, names = FALSE)

  peak_table <- build_peak_demand_forecast(fc, threshold, critical)
  costs <- calculate_tou_cost(fc)
  shifts <- recommend_load_shifts(fc, threshold)
  insights <- energy_insights(history, threshold)
  recs <- generate_recommendations(history, peak_table, insights, threshold)

  public <- result[setdiff(names(result), c("historical", "forecast"))]
  forecast$timestamp <- fmt_ts(forecast$timestamp)
  public$forecast <- forecast
  peak_out <- peak_table
  peak_out$timestamp <- fmt_ts(peak_out$timestamp, "T")
  public$smart_grid <- list(
    historical_average_consumption = insights$average_hourly_consumption,
    historical_maximum_consumption = insights$maximum_hourly_consumption,
    forecast_average_consumption = mean(fc$predicted),
    highest_predicted_demand = max(fc$predicted),
    highest_predicted_demand_timestamp = fmt_ts(fc$timestamp[which.max(fc$predicted)]),
    predicted_peak_count = sum(peak_table$is_peak),
    peak_threshold = threshold,
    threshold_type = "User Dataset Threshold",
    critical_threshold = critical,
    demand_severity = as.list(table(peak_table$demand_level)),
    tou_label = "Illustrative TOU tariff used for simulation.",
    tou_baseline_cost = sum(costs$simulated_cost_inr),
    load_shift_count = nrow(shifts),
    total_shiftable_energy = sum(shifts$shiftable_energy_kwh),
    potential_savings = sum(shifts$estimated_savings),
    recommendations = recs,
    peak_demand_forecast = peak_out
  )
  public$historical_series <- data.frame(timestamp = fmt_ts(history$timestamp), energy_kwh = history$energy_kwh)
  public
}
