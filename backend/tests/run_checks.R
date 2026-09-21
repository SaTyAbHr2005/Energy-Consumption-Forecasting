# Offline self-check for the R backend (no Supabase needed). From the project root:
#   Rscript backend/tests/run_checks.R
# Fails loudly (non-zero exit) if any check breaks.

for (f in list.files("backend/R", pattern = "\\.R$", full.names = TRUE)) source(f)

check <- function(name, ok) {
  cat(sprintf("%s  %s\n", if (isTRUE(ok)) "PASS" else "FAIL", name))
  if (!isTRUE(ok)) quit(status = 1)
}
near <- function(a, b, tol = 1e-6) isTRUE(all.equal(as.numeric(a), as.numeric(b), tolerance = tol))

fx <- "backend/tests/fixtures"

# --- parity with the original Python forecaster -------------------------------
# Expected values were produced by the old Python backend's own code path
# (build_features + XGBRegressor), using the Python-trained model kept in fixtures/, so this check
# keeps validating feature parity and cross-language model loading even after the R pipeline
# retrains models/final/. Two cut points: one lands on midnight Monday, the
# other on a mid-day hour so the calendar/cyclical features are non-trivial.
# UPLOAD_DIR/<id>.csv is where load_hourly() looks first, so no database is needed.
parity_case <- function(expected_file, rows = NULL) {
  expected <- jsonlite::fromJSON(file.path(fx, expected_file))
  csv <- utils::read.csv(file.path(fx, "history.csv"), stringsAsFactors = FALSE)
  if (!is.null(rows)) csv <- head(csv, rows)
  case <- sub("\\.json$", "", expected_file)
  id <- paste0("fixture-", gsub("_", "-", case))
  utils::write.csv(csv, file.path(UPLOAD_DIR, paste0(id, ".csv")), row.names = FALSE)
  tag <- paste0("[", case, "] ")

  history <- load_hourly(id)
  check(paste0(tag, "15-minute readings resample to the same number of hourly rows"), nrow(history) == expected$hours)
  p90 <- quantile(history$energy_kwh, 0.90, names = FALSE)
  check(paste0(tag, "peak threshold (90th percentile) matches Python"), near(p90, expected$threshold))
  next_ts <- history$timestamp[nrow(history)] + 3600
  check(paste0(tag, "next timestamp matches"), fmt_ts(next_ts) == expected$next_timestamp)

  features <- names(expected$features)
  row <- next_hour_features(history, next_ts, p90, features)
  bad <- features[!mapply(function(n) near(row[[n]], expected$features[[n]], 1e-6), features)]
  check(sprintf("%sall %d features match Python%s", tag, length(features),
                if (length(bad)) paste(" (differ:", paste(bad, collapse = ", "), ")") else ""), length(bad) == 0)

  pred <- predict_next_hour(history, next_ts, p90, features, file.path(fx, "python_xgboost_1h.json"))
  check(sprintf("%sXGBoost 1h prediction %.6f matches Python %.6f", tag, pred, expected$prediction),
        near(pred, expected$prediction, 1e-4))
}
parity_case("expected.json")
parity_case("expected_cut.json", rows = jsonlite::fromJSON(file.path(fx, "expected_cut.json"))$rows)

# --- rolling / EWM helpers vs pandas (including gaps, which the real dataset has) ------
gappy <- c(NA, 1, 2.5, NA, NA, 5, 4, NA, 0.5, 3)
check("ewm span=3 matches pandas across gaps",
      near(ewm_mean(gappy, 3), c(NA, 1, 1.75, 1.75, 1.75, 4.35, 4.175, 4.175, 1.725, 2.3625)))
check("ewm span=24 matches pandas across gaps",
      near(ewm_mean(gappy, 24), c(NA, 1, 1.12, 1.12, 1.12, 1.481481702318, 1.682963166133, 1.682963166133, 1.580807452304, 1.69434285612), 1e-9))
series <- c(1, 2, 4, NA, 3, 5, 8, 2, 6, 1)
check("rolling mean (NA window -> NA) matches pandas",
      near(roll_stat(series, 3, "mean"), c(NA, NA, 2.333333333333, NA, NA, NA, 5.333333333333, 5, 5.333333333333, 3), 1e-9))
check("rolling sample std matches pandas",
      near(roll_stat(series, 3, "sd"), c(NA, NA, 1.527525231652, NA, NA, NA, 2.516611478424, 3, 3.055050463304, 2.645751311065), 1e-9))
check("rolling median matches pandas", near(roll_stat(series, 3, "median"), c(NA, NA, 2, NA, NA, NA, 5, 5, 6, 2)))

# --- validator ----------------------------------------------------------------
write_csv <-function(lines) { p <- tempfile(fileext = ".csv"); writeLines(lines, p); p }
hours <- format(seq(as.POSIXct("2026-01-01", tz = "UTC"), by = "hour", length.out = 24 * 8), "%Y-%m-%d %H:%M:%S")

ok <- validate_user_csv(write_csv(c("timestamp,energy_consumption", paste0(hours, ",0.5"))))
check("valid hourly CSV is VALID", ok$status == "VALID")
check("interval reported as pandas-style timedelta", ok$detected_interval == "0 days 01:00:00")
check("8 days of history is 'Basic' readiness", ok$forecasting_readiness == "Basic")

neg <- validate_user_csv(write_csv(c("timestamp,energy_consumption", "2026-01-01 00:00:00,-1")))
check("negative energy is rejected", neg$status == "INVALID" && length(neg$errors) == 1)

bad <- validate_user_csv(write_csv(c("timestamp,energy_consumption", "not-a-date,1")))
check("unparseable timestamp is rejected", bad$status == "INVALID")

nocol <- validate_user_csv(write_csv(c("time,kwh", "2026-01-01 00:00:00,1")))
check("missing required columns are rejected", nocol$status == "INVALID")

# --- smart-grid rules ----------------------------------------------------------
check("TOU: 18:00 is peak", tou_period(18) == "peak")
check("TOU: 03:00 is off_peak", tou_period(3) == "off_peak")
check("TOU: 10:00 is normal", tou_period(10) == "normal")

day <- data.frame(timestamp = as.POSIXct("2026-01-01", tz = "UTC") + 3600 * 0:23, predicted = rep(1, 24))
day$predicted[19] <- 3 # 18:00 spike
table <- build_peak_demand_forecast(day, threshold = 2, critical = 2.5)
check("spike is classified Critical", table$demand_level[19] == "Critical" && sum(table$is_peak) == 1)
shifts <- recommend_load_shifts(day, threshold = 2)
check("load shift moves energy to a cheaper hour and saves money", nrow(shifts) == 1 && shifts$estimated_savings > 0)

# --- bill OCR parsing (text captured from two real MSEDCL bills; no OCR engine needed) ----------
read_ocr <- function(f) paste(readLines(file.path(fx, f), encoding = "UTF-8"), collapse = "\n")
ocr_a <- parse_bill_text(read_ocr("bill_sep2026_a.ocr.txt"))
check("bill A: September 2026, amount 1190, units 129",
      identical(ocr_a$bill_date, "September 2026") && near(ocr_a$cost, 1190) && near(ocr_a$consumption, 129))
ocr_b <- parse_bill_text(read_ocr("bill_sep2026_b.ocr.txt"))
check("bill B: September 2026, amount 640, units 76",
      identical(ocr_b$bill_date, "September 2026") && near(ocr_b$cost, 640) && near(ocr_b$consumption, 76))
check("meter-row fallback reads the units", near(parse_bill_units("x 1221 1.00 129 0 129 y", list(month = 9L, year = 2026L)), 129))
check("unreadable text yields NA, never invented numbers", is.na(parse_bill_text("hello world")$cost))

cat("\nAll checks passed.\n")
