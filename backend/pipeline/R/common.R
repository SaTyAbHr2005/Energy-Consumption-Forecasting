# Shared helpers for the data + ML pipeline (run from the project root).
Sys.setenv(TZ = "UTC")

# The API modules double as the pipeline's library: time helpers, the shared feature
# builder and the smart-grid calculations live in backend/R.
for (f in c("utils.R", "features.R", "smart_grid.R")) source(file.path("backend", "R", f))

DATA_RAW <- file.path(ROOT, "data", "raw")
DATA_PROCESSED <- file.path(ROOT, "data", "processed")
RESULTS <- file.path(ROOT, "results")
FIGURES <- file.path(RESULTS, "figures")
DOCS <- file.path(ROOT, "docs")
for (d in c(DATA_RAW, DATA_PROCESSED, ANALYTICS, METRICS, PREDICTIONS, FIGURES, MODELS, DOCS)) {
  dir.create(d, showWarnings = FALSE, recursive = TRUE)
}

RAW_FILE <- file.path(DATA_RAW, "household_power_consumption.txt")
HOURLY_FILE <- file.path(DATA_PROCESSED, "uci_hourly.parquet")
CLEAN_FILE <- file.path(DATA_PROCESSED, "uci_hourly_clean.parquet")
FEATURES_FILE <- file.path(DATA_PROCESSED, "forecast_features.parquet")

banner <- function(title) cat("\n", strrep("=", 60), "\n", title, "\n", strrep("=", 60), "\n", sep = "")

write_json_file <- function(x, path) {
  dir.create(dirname(path), showWarnings = FALSE, recursive = TRUE)
  jsonlite::write_json(x, path, auto_unbox = TRUE, pretty = TRUE, digits = NA, na = "null", null = "null")
}
read_json_file <- function(path) jsonlite::fromJSON(path, simplifyVector = FALSE)

write_csv_file <- function(df, path) {
  dir.create(dirname(path), showWarnings = FALSE, recursive = TRUE)
  utils::write.csv(df, path, row.names = FALSE, na = "")
}

read_parquet_file <- function(path) as.data.frame(arrow::read_parquet(path))
write_parquet_file <- function(df, path) arrow::write_parquet(df, path)

# Local Spark session (UTC so timestamps are never shifted).
spark_session <- function(app_name) {
  cfg <- sparklyr::spark_config()
  cfg$spark.sql.session.timeZone <- "UTC"
  cfg$spark.driver.memory <- Sys.getenv("SPARK_DRIVER_MEMORY", "4g")
  cfg$spark.ui.enabled <- "false"
  cfg$spark.sql.catalogImplementation <- "in-memory" # no Hive metastore_db/ or derby.log in the project
  sparklyr::spark_connect(master = "local", app_name = app_name, config = cfg)
}

# Run a Spark SQL query and return the result as an R data.frame.
sql_df <- function(sc, query) as.data.frame(dplyr::collect(sparklyr::sdf_sql(sc, query)))
# Register a Spark SQL query result as a named temp view.
sql_view <- function(sc, name, query) {
  sparklyr::sdf_register(sparklyr::sdf_sql(sc, query), name)
  invisible(name)
}

# --- plotting ----------------------------------------------------------------
save_plot <- function(plot, name, width = 10, height = 6, dir = FIGURES) {
  dir.create(dir, showWarnings = FALSE, recursive = TRUE)
  ggplot2::ggsave(file.path(dir, name), plot, width = width, height = height, dpi = 100)
  invisible(plot)
}
theme_energy <- function() ggplot2::theme_minimal(base_size = 12)

# --- statistics --------------------------------------------------------------
skewness <- function(x) { # pandas Series.skew(): adjusted Fisher-Pearson
  x <- x[!is.na(x)]
  n <- length(x)
  m <- mean(x)
  sqrt(n * (n - 1)) / (n - 2) * (sum((x - m)^3) / n) / (sum((x - m)^2) / n)^1.5
}
