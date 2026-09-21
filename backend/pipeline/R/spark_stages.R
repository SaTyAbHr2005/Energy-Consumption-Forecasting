# Spark (sparklyr) stages: raw minute data -> hourly -> cleaned -> basic feature table.
# Ports of src/spark_processor.py, src/preprocessor.py and src/feature_engineering.py.

UCI_COLUMNS <- c(Date = "character", Time = "character", Global_active_power = "double",
                 Global_reactive_power = "double", Voltage = "double", Global_intensity = "double",
                 Sub_metering_1 = "double", Sub_metering_2 = "double", Sub_metering_3 = "double")

null_count_sql <- function(cols, view) {
  parts <- sprintf("SUM(CASE WHEN `%s` IS NULL THEN 1 ELSE 0 END) AS `%s`", cols, cols)
  sprintf("SELECT %s FROM %s", paste(parts, collapse = ", "), view)
}

# --- 1. raw 1-minute readings -> hourly ---------------------------------------
# Returns list(hourly = data.frame, summary = list).
spark_hourly_aggregate <- function(sc, raw_path) {
  raw <- sparklyr::spark_read_csv(sc, "uci_raw", raw_path, delimiter = ";", header = TRUE,
                                  null_value = "?", infer_schema = FALSE, columns = UCI_COLUMNS)
  total_records <- sparklyr::sdf_nrow(raw)
  partitions <- sparklyr::sdf_num_partitions(raw)

  # Global_active_power is kW averaged over one minute -> kWh consumed in that minute = kW / 60.
  sql_view(sc, "uci_processed", "
    SELECT *, to_timestamp(concat_ws(' ', Date, Time), 'd/M/yyyy HH:mm:ss') AS timestamp,
              Global_active_power / 60.0 AS energy_kwh
    FROM uci_raw")

  numeric_cols <- setdiff(names(UCI_COLUMNS), c("Date", "Time"))
  missing <- as.list(sql_df(sc, null_count_sql(numeric_cols, "uci_processed")))
  names(missing) <- paste0("missing_", numeric_cols)
  bounds <- sql_df(sc, "SELECT MIN(timestamp) AS s, MAX(timestamp) AS e FROM uci_processed")

  hourly <- sql_df(sc, "
    SELECT date_trunc('hour', timestamp) AS timestamp,
           SUM(energy_kwh) AS energy_kwh,
           AVG(Global_active_power) AS avg_global_active_power,
           AVG(Global_reactive_power) AS avg_global_reactive_power,
           AVG(Voltage) AS avg_voltage,
           AVG(Global_intensity) AS avg_global_intensity,
           SUM(Sub_metering_1) AS total_sub_metering_1,
           SUM(Sub_metering_2) AS total_sub_metering_2,
           SUM(Sub_metering_3) AS total_sub_metering_3
    FROM uci_processed GROUP BY date_trunc('hour', timestamp) ORDER BY timestamp")

  list(hourly = hourly, summary = list(
    dataset = "UCI Individual Household Electric Power Consumption",
    records = total_records, columns = length(UCI_COLUMNS), missing_values = lapply(missing, as.numeric),
    start_timestamp = fmt_ts(bounds$s), end_timestamp = fmt_ts(bounds$e),
    partitions = partitions, hourly_records = nrow(hourly), processing_status = "success"))
}

# --- 2. preprocessing ---------------------------------------------------------
# Continuous hourly index, short-gap interpolation, outlier flags.
# Returns list(clean = data.frame, report = list).
preprocess_hourly <- function(sc, hourly) {
  report <- list(preprocessing_status = "started", input_records = nrow(hourly))
  sparklyr::sdf_copy_to(sc, hourly, "hourly_in", overwrite = TRUE)

  # timestamps
  sql_view(sc, "t_valid", "SELECT * FROM hourly_in WHERE timestamp IS NOT NULL")
  n_valid <- sql_df(sc, "SELECT COUNT(*) AS n FROM t_valid")$n
  bounds <- sql_df(sc, "SELECT MIN(timestamp) AS s, MAX(timestamp) AS e FROM t_valid")
  report$null_timestamps_removed <- nrow(hourly) - n_valid
  report$start_timestamp <- fmt_ts(bounds$s)
  report$end_timestamp <- fmt_ts(bounds$e)

  # duplicates: sum the energy / sub-metering totals, average everything else
  report$records_before_dedup <- n_valid
  dupes <- sql_df(sc, "SELECT COUNT(*) AS n FROM (SELECT timestamp FROM t_valid GROUP BY timestamp HAVING COUNT(*) > 1)")$n
  report$duplicate_timestamps <- dupes
  if (dupes > 0) {
    cols <- setdiff(names(hourly), "timestamp")
    agg <- ifelse(grepl("^total_", cols) | cols == "energy_kwh",
                  sprintf("SUM(`%s`) AS `%s`", cols, cols), sprintf("AVG(`%s`) AS `%s`", cols, cols))
    sql_view(sc, "t_dedup", sprintf("SELECT timestamp, %s FROM t_valid GROUP BY timestamp", paste(agg, collapse = ", ")))
  } else {
    sql_view(sc, "t_dedup", "SELECT * FROM t_valid")
  }
  report$records_after_dedup <- sql_df(sc, "SELECT COUNT(*) AS n FROM t_dedup")$n

  # continuous hourly series (missing hours become all-null rows)
  cols <- names(hourly)
  sql_view(sc, "t_cont", sprintf("
    SELECT s.timestamp, %s FROM (
      SELECT explode(sequence(to_timestamp('%s'), to_timestamp('%s'), interval 1 hour)) AS timestamp) s
    LEFT JOIN t_dedup d ON s.timestamp = d.timestamp ORDER BY s.timestamp",
    paste(sprintf("d.`%s`", setdiff(cols, "timestamp")), collapse = ", "), report$start_timestamp, report$end_timestamp))
  report$expected_hourly_records <- sql_df(sc, "SELECT COUNT(*) AS n FROM t_cont")$n
  report$actual_hourly_records <- report$records_after_dedup
  report$missing_hourly_records <- report$expected_hourly_records - report$actual_hourly_records

  # missing values: gaps of <= 3 hours are interpolated between the neighbouring readings
  numeric_cols <- cols[vapply(hourly, is.numeric, logical(1))]
  report$missing_values_before <- lapply(as.list(sql_df(sc, null_count_sql(numeric_cols, "t_cont"))), as.numeric)
  select_cols <- ifelse(cols == "energy_kwh",
                        "CASE WHEN is_missing = 1 AND gap_size <= 3 THEN (ffill_energy + bfill_energy) / 2.0 ELSE energy_kwh END AS energy_kwh",
                        sprintf("`%s`", cols))
  sql_view(sc, "t_filled", sprintf("
    WITH a AS (SELECT *, CASE WHEN energy_kwh IS NULL THEN 1 ELSE 0 END AS is_missing FROM t_cont),
         b AS (SELECT *, SUM(CASE WHEN is_missing = 0 THEN 1 ELSE 0 END) OVER (ORDER BY timestamp) AS gap_group FROM a),
         c AS (SELECT *,
                 CASE WHEN is_missing = 1 THEN SUM(is_missing) OVER (PARTITION BY gap_group) ELSE 0 END AS gap_size,
                 LAST(energy_kwh, true) OVER (ORDER BY timestamp) AS ffill_energy,
                 FIRST(energy_kwh, true) OVER (ORDER BY timestamp ROWS BETWEEN CURRENT ROW AND UNBOUNDED FOLLOWING) AS bfill_energy
               FROM b)
    SELECT %s, CASE WHEN gap_size > 3 THEN 1 ELSE 0 END AS is_long_gap FROM c ORDER BY timestamp",
    paste(select_cols, collapse = ", ")))
  report$missing_values_after <- lapply(as.list(sql_df(sc, null_count_sql(numeric_cols, "t_filled"))), as.numeric)

  # outliers: IQR rule on energy_kwh
  q <- unlist(sql_df(sc, "SELECT percentile(energy_kwh, array(0.25, 0.75)) AS q FROM t_filled")$q)
  iqr <- q[2] - q[1]
  lower <- q[1] - 1.5 * iqr
  upper <- q[2] + 1.5 * iqr
  sql_view(sc, "t_flagged", sprintf(
    "SELECT *, CASE WHEN energy_kwh > %.12f OR energy_kwh < %.12f THEN 1 ELSE 0 END AS is_energy_outlier FROM t_filled",
    upper, lower))
  report$outlier_count <- sql_df(sc, "SELECT SUM(is_energy_outlier) AS n FROM t_flagged")$n
  report$outlier_lower_bound <- lower
  report$outlier_upper_bound <- upper

  # energy can never be negative
  report$negative_energy_values <- sql_df(sc, "SELECT COUNT(*) AS n FROM t_flagged WHERE energy_kwh < 0")$n
  clean <- sql_df(sc, "SELECT * FROM t_flagged ORDER BY timestamp")
  clean$energy_kwh <- ifelse(!is.na(clean$energy_kwh) & clean$energy_kwh < 0, 0, clean$energy_kwh)

  report$output_records <- nrow(clean)
  report$preprocessing_status <- "success"
  list(clean = clean, report = report)
}

# --- 3. basic feature table (Spark window functions) ----------------------------
BASIC_LAGS <- c(1, 3, 6, 12, 24, 48, 72, 168)
BASIC_ROLLING <- c(3, 6, 12, 24, 168)

# Returns list(features = data.frame, summary = list, correlations = matrix).
spark_basic_features <- function(sc, clean) {
  sparklyr::sdf_copy_to(sc, clean, "clean_in", overwrite = TRUE)
  p90 <- sql_df(sc, "SELECT percentile(energy_kwh, 0.9) AS p FROM clean_in")$p
  order_by <- "OVER (ORDER BY timestamp)"

  lag_sql <- sprintf("LAG(energy_kwh, %d) %s AS lag_%d", BASIC_LAGS, order_by, BASIC_LAGS)
  roll_sql <- sprintf("AVG(energy_kwh) OVER (ORDER BY timestamp ROWS BETWEEN %d PRECEDING AND 1 PRECEDING) AS rolling_mean_%d",
                      BASIC_ROLLING, BASIC_ROLLING)
  win24 <- "OVER (ORDER BY timestamp ROWS BETWEEN 24 PRECEDING AND 1 PRECEDING)"
  sql_view(sc, "feat_all", sprintf("
    WITH cal AS (
      SELECT *, year(timestamp) AS year, month(timestamp) AS month, dayofmonth(timestamp) AS day,
             dayofmonth(timestamp) AS day_of_month, (dayofweek(timestamp) + 5) %% 7 AS day_of_week,
             hour(timestamp) AS hour, weekofyear(timestamp) AS week_of_year, quarter(timestamp) AS quarter
      FROM clean_in),
    cyc AS (
      SELECT *, CASE WHEN day_of_week IN (5, 6) THEN 1 ELSE 0 END AS is_weekend,
             sin(2 * pi() * hour / 24) AS hour_sin, cos(2 * pi() * hour / 24) AS hour_cos,
             sin(2 * pi() * day_of_week / 7) AS dow_sin, cos(2 * pi() * day_of_week / 7) AS dow_cos,
             sin(2 * pi() * month / 12) AS month_sin, cos(2 * pi() * month / 12) AS month_cos
      FROM cal),
    lagged AS (SELECT *, %s FROM cyc),
    rolled AS (
      SELECT *, %s,
             STDDEV(energy_kwh) %s AS rolling_std_24, MIN(energy_kwh) %s AS rolling_min_24, MAX(energy_kwh) %s AS rolling_max_24
      FROM lagged)
    SELECT *, lag_1 - lag_3 AS trend_3h, lag_1 - lag_24 AS trend_24h,
              CASE WHEN lag_1 >= %.12f THEN 1 ELSE 0 END AS is_high_demand_previous_hour
    FROM rolled ORDER BY timestamp",
    paste(lag_sql, collapse = ", "), paste(roll_sql, collapse = ", "), win24, win24, win24, p90))

  all_cols <- names(sql_df(sc, "SELECT * FROM feat_all LIMIT 1"))
  count_nulls <- function(view) sum(unlist(sql_df(sc, null_count_sql(all_cols, view))))
  missing_before <- count_nulls("feat_all")
  # burn-in: drop rows without a full 168-hour history, then any row still containing a null
  keep <- paste(sprintf("`%s` IS NOT NULL", all_cols), collapse = " AND ")
  sql_view(sc, "feat_final", sprintf("SELECT * FROM feat_all WHERE lag_168 IS NOT NULL AND %s ORDER BY timestamp", keep))
  features <- sql_df(sc, "SELECT * FROM feat_final ORDER BY timestamp")

  names_out <- setdiff(names(features), c("timestamp", "energy_kwh"))
  corr_cols <- intersect(c("energy_kwh", "lag_1", "lag_3", "lag_6", "lag_12", "lag_24", "lag_48", "lag_72", "lag_168",
                           "rolling_mean_3", "rolling_mean_6", "rolling_mean_12", "rolling_mean_24", "rolling_mean_168"),
                         names(features))
  list(features = features,
       correlations = stats::cor(features[corr_cols], use = "pairwise.complete.obs"),
       summary = list(input_records = nrow(clean), output_records = nrow(features),
                      features_created = length(names_out), feature_names = names_out,
                      rows_removed_for_history = nrow(clean) - nrow(features),
                      missing_values_before = missing_before, missing_values_after = count_nulls("feat_final"),
                      target_column = "energy_kwh"))
}
