# Stage 5 (Spark): basic calendar / lag / rolling feature table used by the baseline models.
source("backend/pipeline/R/common.R")
source("backend/pipeline/R/spark_stages.R")

banner("Feature engineering pipeline")
sc <- spark_session("FeatureEngineering")
tryCatch({
  res <- spark_basic_features(sc, read_parquet_file(CLEAN_FILE))
  s <- res$summary
  cat("Input records:", s$input_records, "\n")
  cat("Output records:", s$output_records, "\n")
  cat("Features created:", s$features_created, "\n")
  cat("Rows removed for insufficient history:", s$rows_removed_for_history, "\n")
  cat("Remaining null values:", s$missing_values_after, "\n")
  write_parquet_file(res$features, FEATURES_FILE)
  write_json_file(s, file.path(METRICS, "feature_summary.json"))
  corr <- cbind(` ` = rownames(res$correlations), as.data.frame(res$correlations))
  utils::write.csv(corr, file.path(ANALYTICS, "feature_correlations.csv"), row.names = FALSE)
  cat("Saved", FEATURES_FILE, "\n")
}, finally = sparklyr::spark_disconnect(sc))
