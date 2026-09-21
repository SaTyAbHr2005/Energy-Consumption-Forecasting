# Stage 1: download the UCI Individual Household Electric Power Consumption dataset.
source("backend/pipeline/R/common.R")

url <- "https://archive.ics.uci.edu/static/public/235/individual+household+electric+power+consumption.zip"
zip_path <- file.path(DATA_RAW, "household_power_consumption.zip")

if (file.exists(RAW_FILE)) {
  cat("Dataset already exists at", RAW_FILE, "- skipping download.\n")
} else {
  cat("Downloading dataset from", url, "...\n")
  options(timeout = 3600)
  ok <- tryCatch({
    utils::download.file(url, zip_path, mode = "wb", quiet = TRUE)
    utils::unzip(zip_path, exdir = DATA_RAW)
    unlink(zip_path)
    file.exists(RAW_FILE)
  }, error = function(e) { cat("Error downloading dataset:", conditionMessage(e), "\n"); FALSE })
  if (!ok) stop("Dataset download failed; expected file not found: ", RAW_FILE)
  cat("Dataset is ready at", RAW_FILE, "\n")
}
