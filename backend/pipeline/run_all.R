# Runs the whole data + ML pipeline, stage by stage, from the project root:
#   Rscript backend/pipeline/run_all.R            # all stages
#   Rscript backend/pipeline/run_all.R 6 7 8 9    # only the listed stages (by number)
# Every stage runs in its own R process so a Spark session never leaks into the next one.
stages <- c(
  "01_download.R", "02_spark_hourly.R", "03_preprocess.R", "04_eda.R", "05_features.R",
  "06_train_models.R", "07_evaluate.R", "08_optimize.R", "09_smart_grid.R", "10_audit.R"
)
wanted <- as.integer(commandArgs(trailingOnly = TRUE))
if (length(wanted) > 0) stages <- stages[wanted]

rscript <- file.path(R.home("bin"), "Rscript")
started <- Sys.time()
for (stage in stages) {
  cat("\n>>>", stage, "\n")
  t0 <- Sys.time()
  status <- system2(rscript, file.path("backend", "pipeline", stage))
  if (status != 0) stop(sprintf("Stage %s failed (exit code %d)", stage, status), call. = FALSE)
  cat(sprintf("<<< %s finished in %.0f s\n", stage, as.numeric(difftime(Sys.time(), t0, units = "secs"))))
}
cat(sprintf("\nPipeline complete in %.1f minutes.\n", as.numeric(difftime(Sys.time(), started, units = "mins"))))
