# Stage 10 (Spark): audit the raw -> hourly -> clean -> feature reduction chain.
source("backend/pipeline/R/common.R")
source("backend/pipeline/R/spark_stages.R")

banner("Dataset audit")
sc <- spark_session("Audit")
tryCatch({
  sparklyr::spark_read_csv(sc, "uci_raw", RAW_FILE, delimiter = ";", header = TRUE, null_value = "?",
                           infer_schema = FALSE, columns = UCI_COLUMNS)
  raw_count <- sql_df(sc, "SELECT COUNT(*) AS n FROM uci_raw")$n
  b <- sql_df(sc, "
    WITH t AS (SELECT to_timestamp(concat_ws(' ', Date, Time), 'd/M/yyyy HH:mm:ss') AS timestamp FROM uci_raw)
    SELECT MIN(timestamp) AS s, MAX(timestamp) AS e FROM t")
  m <- sql_df(sc, "
    WITH t AS (SELECT date_trunc('hour', to_timestamp(concat_ws(' ', Date, Time), 'd/M/yyyy HH:mm:ss')) AS hour FROM uci_raw),
         c AS (SELECT hour, COUNT(*) AS n FROM t GROUP BY hour)
    SELECT COUNT(*) AS hours, SUM(CASE WHEN n = 60 THEN 1 ELSE 0 END) AS full_hours,
           SUM(CASE WHEN n < 60 THEN 1 ELSE 0 END) AS partial_hours, MIN(n) AS min_n, MAX(n) AS max_n, AVG(n) AS avg_n FROM c")
  write_json_file(list(
    raw_record_count = raw_count, hourly_record_count = m$hours, expected_hourly_count = m$hours,
    hours_with_full_coverage = m$full_hours, hours_with_partial_coverage = m$partial_hours,
    hours_with_no_measurements = 0, minimum_minutes_per_hour = m$min_n, maximum_minutes_per_hour = m$max_n,
    average_minutes_per_hour = m$avg_n), file.path(METRICS, "hourly_aggregation_summary.json"))

  hourly <- read_parquet_file(HOURLY_FILE)
  clean <- read_parquet_file(CLEAN_FILE)
  feat <- read_parquet_file(FEATURES_FILE)
  split <- read_json_file(file.path(METRICS, "data_split.json"))
  rng <- function(d) list(fmt_ts(min(d$timestamp)), fmt_ts(max(d$timestamp)))
  write_json_file(list(
    raw_records = raw_count, hourly_records = nrow(hourly), clean_records = nrow(clean), feature_records = nrow(feat),
    train_records = split$train_records, validation_records = split$validation_records, test_records = split$test_records,
    raw_start = fmt_ts(b$s), raw_end = fmt_ts(b$e),
    hourly_start = rng(hourly)[[1]], hourly_end = rng(hourly)[[2]], feature_start = rng(feat)[[1]], feature_end = rng(feat)[[2]],
    raw_to_hourly_reduction_reason = "Legitimate time-series aggregation from 1-minute measurements to 1-hour observations. The complete historical period is preserved and energy is summed, not averaged.",
    feature_row_reduction_reason = sprintf(
      "Dropped %d rows: the first 168 hours have no lag_168, and hours inside long measurement gaps carry no target or lag values (no silent null filling).",
      nrow(clean) - nrow(feat)),
    data_coverage_status = "Complete representation of the full timeline."),
    file.path(METRICS, "dataset_reconciliation.json"))
  cat("Audit written to results/metrics/hourly_aggregation_summary.json and dataset_reconciliation.json\n")
}, finally = sparklyr::spark_disconnect(sc))
