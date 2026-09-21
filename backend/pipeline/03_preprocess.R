# Stage 3 (Spark): continuous hourly index, gap interpolation, outlier flags.
source("backend/pipeline/R/common.R")
source("backend/pipeline/R/spark_stages.R")

banner("Data preprocessing for Smart Home Energy Consumption")
sc <- spark_session("EnergyDataPreprocessing")
tryCatch({
  res <- preprocess_hourly(sc, read_parquet_file(HOURLY_FILE))
  r <- res$report
  cat("Input records:", r$input_records, "\n")
  cat("Duplicate timestamps:", r$duplicate_timestamps, "\n")
  cat("Missing hourly records filled in:", r$missing_hourly_records, "\n")
  cat("Outliers flagged (IQR rule):", r$outlier_count, "\n")
  cat("Output records:", r$output_records, "\n")
  cat("energy_kwh missing:", r$missing_values_before$energy_kwh, "->", r$missing_values_after$energy_kwh, "\n")
  write_parquet_file(res$clean, CLEAN_FILE)
  write_json_file(r, file.path(METRICS, "preprocessing_summary.json"))
  cat("Saved", CLEAN_FILE, "\n")
}, finally = sparklyr::spark_disconnect(sc))
