# Validate a household electricity CSV the same way the API does on upload:
#   Rscript backend/pipeline/validate_user_csv.R path/to/file.csv
for (f in c("utils.R", "validator.R")) source(file.path("backend", "R", f))

args <- commandArgs(trailingOnly = TRUE)
if (length(args) != 1) stop("Usage: Rscript backend/pipeline/validate_user_csv.R <file.csv>")
result <- validate_user_csv(args[1])

cat("\n", strrep("=", 50), "\nUSER CSV VALIDATION REPORT\n", strrep("=", 50), "\n", sep = "")
cat("\nFile:", basename(args[1]), "\nStatus:", result$status, "\n")
if (length(result$errors) > 0) {
  cat("\nERRORS:\n"); for (e in result$errors) cat("  -", e, "\n")
} else {
  cat("Records:", result$records, "\n")
  cat("Date range:", result$start_timestamp, "->", result$end_timestamp, "\n")
  cat("Detected sampling interval:", result$detected_interval, "\n")
  cat("Forecasting readiness:", toupper(result$forecasting_readiness), "\n")
  if (length(result$warnings) > 0) { cat("\nWarnings:\n"); for (w in result$warnings) cat("  -", w, "\n") }
}
cat(strrep("=", 50), "\n")
