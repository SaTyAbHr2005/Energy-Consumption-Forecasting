# Stage 4: exploratory data analysis. Aggregations run in Spark; plots are drawn in R.
# Writes results/analytics/*.csv|json, results/metrics/eda_summary.json and results/figures/*.png.
source("backend/pipeline/R/common.R")
source("backend/pipeline/R/spark_stages.R")
library(ggplot2)

banner("Exploratory data analysis and energy analytics")
DAYS <- c("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")

sc <- spark_session("EnergyEDA")
tryCatch({
  clean_cols <- read_parquet_file(CLEAN_FILE)
  sparklyr::sdf_copy_to(sc, clean_cols, "clean_data", overwrite = TRUE)
  sql_view(sc, "eda", "
    SELECT *, date_trunc('day', timestamp) AS date, hour(timestamp) AS hour, month(timestamp) AS month,
           dayofweek(timestamp) AS dayofweek_num, date_format(timestamp, 'EEEE') AS day_name,
           CASE WHEN dayofweek(timestamp) IN (1, 7) THEN 1 ELSE 0 END AS is_weekend,
           CASE WHEN month(timestamp) IN (12, 1, 2) THEN 'Winter' WHEN month(timestamp) IN (3, 4, 5) THEN 'Spring'
                WHEN month(timestamp) IN (6, 7, 8) THEN 'Summer' ELSE 'Autumn' END AS season
    FROM clean_data")

  # --- overall statistics -----------------------------------------------------
  s <- sql_df(sc, "
    SELECT COUNT(*) AS n, MIN(timestamp) AS s, MAX(timestamp) AS e, AVG(energy_kwh) AS mean, STDDEV(energy_kwh) AS sd,
           VARIANCE(energy_kwh) AS var, MIN(energy_kwh) AS mn, MAX(energy_kwh) AS mx,
           percentile(energy_kwh, array(0.25, 0.5, 0.75, 0.9, 0.95, 0.99)) AS q FROM eda")
  q <- unlist(s$q) # exact percentiles (linear interpolation, like pandas)
  stats <- list(mean = s$mean, median = q[2], min = s$mn, max = s$mx, stddev = s$sd, variance = s$var,
                percentile_25 = q[1], percentile_50 = q[2], percentile_75 = q[3],
                percentile_90 = q[4], percentile_95 = q[5], percentile_99 = q[6])
  p90 <- q[4]
  p95 <- q[5]
  cat("Records:", s$n, " mean:", round(s$mean, 3), " p90:", round(p90, 3), "\n")

  energy <- sql_df(sc, "SELECT timestamp, energy_kwh, hour, day_name, date FROM eda ORDER BY timestamp")

  # --- distribution -----------------------------------------------------------
  save_plot(ggplot(energy, aes(energy_kwh)) + geom_histogram(bins = 50, fill = "skyblue", na.rm = TRUE) +
              labs(title = "Distribution of Hourly Energy Consumption", x = "Energy (kWh)", y = "Frequency") + theme_energy(),
            "energy_distribution.png")
  save_plot(ggplot(energy, aes(energy_kwh)) + geom_boxplot(fill = "lightgreen", na.rm = TRUE) +
              labs(title = "Boxplot of Hourly Energy Consumption (Outliers Preserved)", x = "Energy Consumption (kWh)") + theme_energy(),
            "energy_boxplot.png")

  # --- hourly / daily / weekly / monthly / seasonal --------------------------------
  hourly <- sql_df(sc, "SELECT hour, AVG(energy_kwh) AS avg_energy_kwh FROM eda GROUP BY hour ORDER BY hour")
  write_csv_file(hourly, file.path(ANALYTICS, "hourly_profile.csv"))
  save_plot(ggplot(hourly, aes(hour, avg_energy_kwh)) + geom_line(color = "blue") + geom_point(color = "blue") +
              labs(title = "Average Energy Consumption by Hour of Day", x = "Hour", y = "Avg Energy (kWh)") + theme_energy(),
            "hourly_consumption_pattern.png")

  demand <- sql_df(sc, sprintf("SELECT CASE WHEN energy_kwh >= %.12f THEN 'critical' WHEN energy_kwh >= %.12f THEN 'high'
                                ELSE 'normal' END AS level, COUNT(*) AS n FROM eda GROUP BY 1", p95, p90))
  demand_counts <- setNames(as.list(demand$n), demand$level)
  save_plot(ggplot(energy, aes(timestamp, energy_kwh)) + geom_line(alpha = 0.5, na.rm = TRUE) +
              geom_hline(yintercept = c(p90, p95), color = c("orange", "red"), linetype = "dashed") +
              labs(title = "Energy Consumption with Peak Demand Thresholds (90th / 95th percentile)", x = "Time", y = "Energy (kWh)") +
              theme_energy(), "peak_demand_analysis.png", width = 14)
  high <- sql_df(sc, sprintf("SELECT hour, day_name FROM eda WHERE energy_kwh >= %.12f", p90))
  if (nrow(high) > 0) {
    save_plot(ggplot(as.data.frame(table(hour = high$hour)), aes(hour, Freq)) + geom_col(fill = "#2c7fb8") +
                labs(title = "Number of High Demand Events by Hour", x = "Hour", y = "Count") + theme_energy(), "peak_by_hour.png")
    save_plot(ggplot(as.data.frame(table(day = factor(high$day_name, DAYS))), aes(day, Freq)) + geom_col(fill = "#2c7fb8") +
                labs(title = "Number of High Demand Events by Day", x = "Day of Week", y = "Count") + theme_energy(), "peak_by_weekday.png")
  }

  daily <- sql_df(sc, "SELECT CAST(date AS DATE) AS date, SUM(energy_kwh) AS total_energy_kwh, AVG(energy_kwh) AS mean_energy_kwh,
                       MAX(energy_kwh) AS max_energy_kwh, MIN(energy_kwh) AS min_energy_kwh FROM eda GROUP BY date ORDER BY date")
  write_csv_file(daily, file.path(ANALYTICS, "daily_consumption.csv"))
  save_plot(ggplot(daily, aes(date, total_energy_kwh)) + geom_line(color = "darkgreen", na.rm = TRUE) +
              labs(title = "Daily Energy Consumption Trend", x = "Date", y = "Total Energy (kWh)") + theme_energy(),
            "daily_consumption_trend.png", width = 14)
  daily$rolling_7d <- as.numeric(stats::filter(daily$total_energy_kwh, rep(1 / 7, 7), sides = 1))
  save_plot(ggplot(daily, aes(date)) + geom_line(aes(y = total_energy_kwh), alpha = 0.4, na.rm = TRUE) +
              geom_line(aes(y = rolling_7d), color = "red", na.rm = TRUE) +
              labs(title = "Long Term Trend with 7-Day Rolling Mean", x = "Date", y = "Energy (kWh)") + theme_energy(),
            "rolling_consumption.png", width = 14)

  weekly <- sql_df(sc, "SELECT dayofweek_num, day_name, AVG(energy_kwh) AS avg_energy_kwh FROM eda GROUP BY dayofweek_num, day_name ORDER BY dayofweek_num")
  write_csv_file(weekly, file.path(ANALYTICS, "weekday_profile.csv"))
  save_plot(ggplot(weekly, aes(reorder(day_name, dayofweek_num), avg_energy_kwh)) + geom_col(fill = "#41ab5d") +
              labs(title = "Average Energy Consumption by Day of Week", x = "Day of Week", y = "Avg Energy (kWh)") + theme_energy(),
            "weekday_consumption.png")

  wk <- sql_df(sc, "SELECT is_weekend, AVG(energy_kwh) AS mean, percentile(energy_kwh, 0.5) AS median,
                     SUM(energy_kwh) AS total, MAX(energy_kwh) AS max FROM eda GROUP BY is_weekend")
  weekend_cmp <- list()
  for (i in seq_len(nrow(wk))) {
    weekend_cmp[[if (wk$is_weekend[i] == 1) "weekend" else "weekday"]] <-
      list(mean = wk$mean[i], median = wk$median[i], total = wk$total[i], max = wk$max[i])
  }
  save_plot(ggplot(data.frame(group = names(weekend_cmp), mean = vapply(weekend_cmp, `[[`, 0, "mean")), aes(group, mean)) +
              geom_col(fill = "#6baed6") + labs(title = "Average Consumption: Weekday vs Weekend", x = NULL, y = "Average Energy (kWh)") +
              theme_energy(), "weekday_vs_weekend.png", width = 8)

  heat <- sql_df(sc, "SELECT day_name, hour, AVG(energy_kwh) AS v FROM eda GROUP BY day_name, hour")
  save_plot(ggplot(heat, aes(hour, factor(day_name, rev(DAYS)), fill = v)) + geom_tile() +
              scale_fill_distiller(palette = "YlGnBu", direction = 1, na.value = "grey90") +
              labs(title = "Average Energy Consumption Heatmap", x = "Hour of Day", y = "Day of Week", fill = "kWh") + theme_energy(),
            "hour_day_heatmap.png", width = 14)

  monthly <- sql_df(sc, "SELECT month, SUM(energy_kwh) AS total_energy_kwh, AVG(energy_kwh) AS avg_hourly_energy_kwh,
                          MAX(energy_kwh) AS max_energy_kwh FROM eda GROUP BY month ORDER BY month")
  write_csv_file(monthly, file.path(ANALYTICS, "monthly_consumption.csv"))
  save_plot(ggplot(monthly, aes(factor(month), total_energy_kwh)) + geom_col(fill = "#41ab5d") +
              labs(title = "Total Energy Consumption by Month", x = "Month", y = "Total Energy (kWh)") + theme_energy(),
            "monthly_consumption.png")
  seasonal <- sql_df(sc, "SELECT season, AVG(energy_kwh) AS avg_energy_kwh FROM eda GROUP BY season")
  save_plot(ggplot(seasonal, aes(season, avg_energy_kwh)) + geom_col(fill = "#41ab5d") +
              labs(title = "Average Energy Consumption by Season", x = "Season", y = "Avg Energy (kWh)") + theme_energy(),
            "seasonal_consumption.png")
  long_term <- sql_df(sc, "SELECT date_format(timestamp, 'yyyy-MM') AS ym, SUM(energy_kwh) AS energy_kwh FROM eda GROUP BY 1 ORDER BY 1")
  save_plot(ggplot(long_term, aes(ym, energy_kwh, group = 1)) + geom_line() + geom_point() +
              labs(title = "Long-Term Monthly Total Consumption", x = "Month", y = "Total Energy (kWh)") + theme_energy() +
              theme(axis.text.x = element_text(angle = 45, hjust = 1)), "long_term_consumption.png", width = 14)

  # --- sub-metering ---------------------------------------------------------------
  sm <- sql_df(sc, "SELECT SUM(total_sub_metering_1) AS sm1, SUM(total_sub_metering_2) AS sm2, SUM(total_sub_metering_3) AS sm3 FROM eda")
  sm_total <- sum(unlist(sm), na.rm = TRUE)
  submetering <- lapply(1:3, function(i) list(total = sm[[i]], relative_contribution = if (sm_total > 0) sm[[i]] / sm_total else 0))
  names(submetering) <- paste0("sub_metering_", 1:3)
  write_json_file(submetering, file.path(ANALYTICS, "submetering_profile.json"))
  save_plot(ggplot(data.frame(part = names(submetering), total = vapply(submetering, `[[`, 0, "total")), aes("", total, fill = part)) +
              geom_col(width = 1) + coord_polar("y") + labs(title = "Total Sub-metering Contribution", x = NULL, y = NULL, fill = NULL) +
              theme_void(), "submetering_consumption.png", width = 8, height = 8)

  # --- correlations, variability, autocorrelation ---------------------------------------
  numeric <- sql_df(sc, "SELECT * FROM eda")
  numeric <- numeric[vapply(numeric, is.numeric, logical(1))]
  corr <- stats::cor(numeric, use = "pairwise.complete.obs")
  cm <- as.data.frame(as.table(corr))
  save_plot(ggplot(cm, aes(Var1, Var2, fill = Freq)) + geom_tile() + geom_text(aes(label = sprintf("%.2f", Freq)), size = 2.5) +
              scale_fill_gradient2(low = "steelblue", mid = "white", high = "firebrick", limits = c(-1, 1)) +
              labs(title = "Correlation Matrix of Numeric Features", x = NULL, y = NULL, fill = "r") + theme_energy() +
              theme(axis.text.x = element_text(angle = 45, hjust = 1)), "correlation_matrix.png", width = 10, height = 8)
  target_corr <- as.list(corr["energy_kwh", setdiff(colnames(corr), "energy_kwh")])

  cv <- s$sd / s$mean

  lag_cols <- sprintf("LAG(energy_kwh, %d) OVER (ORDER BY timestamp) AS lag_%d", c(1, 24, 48, 168), c(1, 24, 48, 168))
  autocorr <- as.list(sql_df(sc, sprintf(
    "WITH l AS (SELECT energy_kwh, %s FROM eda) SELECT corr(energy_kwh, lag_1) AS lag_1, corr(energy_kwh, lag_24) AS lag_24,
            corr(energy_kwh, lag_48) AS lag_48, corr(energy_kwh, lag_168) AS lag_168 FROM l", paste(lag_cols, collapse = ", "))))
  save_plot(ggplot(data.frame(lag = factor(names(autocorr), names(autocorr)), r = unlist(autocorr)), aes(lag, r)) +
              geom_col(fill = "#2c7fb8") + labs(title = "Autocorrelation of Energy Consumption at Key Lags",
                                                x = "Lag (Hours)", y = "Autocorrelation Coefficient") + theme_energy(),
            "autocorrelation.png", width = 8)

  # --- summary ------------------------------------------------------------------
  dur <- as.numeric(difftime(s$e, s$s, units = "days"))
  wd_days <- weekly$day_name
  write_json_file(list(
    dataset_overview = list(num_records = s$n, num_variables = length(names(clean_cols)), start_date = fmt_ts(s$s),
                            end_date = fmt_ts(s$e), total_duration_days = round(dur, 2)),
    consumption_statistics = stats,
    hourly_analysis = list(highest_average_consumption_hour = hourly$hour[which.max(hourly$avg_energy_kwh)],
                           lowest_average_consumption_hour = hourly$hour[which.min(hourly$avg_energy_kwh)],
                           max_hourly_average = max(hourly$avg_energy_kwh), min_hourly_average = min(hourly$avg_energy_kwh)),
    weekday_weekend_analysis = list(highest_consumption_weekday = wd_days[which.max(weekly$avg_energy_kwh)],
                                    lowest_consumption_weekday = wd_days[which.min(weekly$avg_energy_kwh)],
                                    weekday_average_kwh = weekend_cmp$weekday$mean, weekend_average_kwh = weekend_cmp$weekend$mean),
    monthly_analysis = list(highest_consumption_month = monthly$month[which.max(monthly$total_energy_kwh)],
                            lowest_consumption_month = monthly$month[which.min(monthly$total_energy_kwh)]),
    peak_demand_analysis = list(percentile_90_threshold = p90, percentile_95_threshold = p95,
                                maximum_observed_demand = s$mx, high_demand_hours_count = demand_counts$high %||% 0,
                                critical_demand_hours_count = demand_counts$critical %||% 0),
    submetering_analysis = submetering,
    variability_analysis = list(overall_cv = cv, overall_stddev = s$sd),
    correlation_analysis = target_corr,
    autocorrelation_analysis = autocorr),
    file.path(METRICS, "eda_summary.json"))
  cat("EDA completed: results/metrics/eda_summary.json\n")
}, finally = sparklyr::spark_disconnect(sc))
