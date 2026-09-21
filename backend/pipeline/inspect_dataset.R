# Inspect the downloaded UCI dataset (read-only):  Rscript backend/pipeline/inspect_dataset.R
source("backend/pipeline/R/common.R")

if (!file.exists(RAW_FILE)) stop("Dataset not found at ", RAW_FILE, ". Run backend/pipeline/01_download.R first.")
cat("Loading dataset for inspection. This might take a moment...\n")
df <- data.table::fread(RAW_FILE, sep = ";", na.strings = "?")

banner("DATASET INSPECTION REPORT")
cat(sprintf("File name: %s\nFile size: %.2f MB\n", basename(RAW_FILE), file.size(RAW_FILE) / 1024^2))
cat("Number of records (rows):", nrow(df), "\nNumber of columns:", ncol(df), "\n")
cat("\nColumn names:\n"); print(names(df))
cat("\n--- First 5 records ---\n"); print(head(df, 5))
cat("\n--- Last 5 records ---\n"); print(tail(df, 5))
cat("\n--- Data types ---\n"); print(vapply(df, function(x) class(x)[1], ""))
cat("\n--- Missing values per column ---\n"); print(colSums(is.na(df)))
dates <- as.Date(df$Date, format = "%d/%m/%Y")
cat("\nApproximate date range:", format(min(dates, na.rm = TRUE)), "to", format(max(dates, na.rm = TRUE)), "\n")
cat("\n--- Descriptive statistics for numeric columns ---\n")
print(summary(df[, vapply(df, is.numeric, logical(1)), with = FALSE]))
