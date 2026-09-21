# Stage 2 (Spark): 2M one-minute readings -> hourly kWh, sub-metering totals and averages.
source("backend/pipeline/R/common.R")
source("backend/pipeline/R/spark_stages.R")

banner("Spark processing for Smart Home Energy Consumption")
if (!file.exists(RAW_FILE)) stop("Raw dataset not found at ", RAW_FILE, ". Run 01_download.R first.")

sc <- spark_session("SmartGridEnergyProcessing")
tryCatch({
  res <- spark_hourly_aggregate(sc, RAW_FILE)
  cat("Records loaded:", res$summary$records, "in", res$summary$partitions, "partitions\n")
  cat("Period:", res$summary$start_timestamp, "->", res$summary$end_timestamp, "\n")
  cat("Hourly records generated:", res$summary$hourly_records, "\n")
  write_parquet_file(res$hourly, HOURLY_FILE)
  write_json_file(res$summary, file.path(METRICS, "spark_processing_summary.json"))
  cat("Saved", HOURLY_FILE, "\n")
}, finally = sparklyr::spark_disconnect(sc))
