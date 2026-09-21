# CSV upload validation (port of src/user_data_validator.py) and dataset storage.

format_timedelta <- function(secs) {
  secs <- as.integer(round(secs))
  rem <- secs %% 86400L
  sprintf("%d days %02d:%02d:%02d", secs %/% 86400L, rem %/% 3600L, (rem %% 3600L) %/% 60L, rem %% 60L)
}

validate_user_csv <- function(path) {
  errors <- character()
  warnings <- character()
  records <- 0L
  start_ts <- end_ts <- interval <- interval_secs <- NULL
  readiness <- "Unknown"

  result <- function(status) {
    list(status = status, records = records, start_timestamp = start_ts, end_timestamp = end_ts,
         detected_interval = interval, interval_seconds = interval_secs,
         forecasting_readiness = readiness, warnings = as.list(warnings), errors = as.list(errors))
  }

  if (!file.exists(path) || file.size(path) == 0) {
    errors <- "File is empty."
    return(result("INVALID"))
  }
  df <- tryCatch(
    utils::read.csv(path, stringsAsFactors = FALSE, check.names = FALSE, na.strings = c("", "NA", "NaN")),
    error = function(e) e
  )
  if (inherits(df, "error")) {
    errors <- paste("Failed to parse CSV:", conditionMessage(df))
    return(result("INVALID"))
  }
  if (nrow(df) == 0) {
    errors <- "CSV has no data rows."
    return(result("INVALID"))
  }
  records <- nrow(df)

  missing_cols <- setdiff(c("timestamp", "energy_consumption"), names(df))
  if (length(missing_cols) > 0) {
    errors <- paste("Missing required column:", missing_cols)
    return(result("INVALID"))
  }

  ts_raw <- as.character(df$timestamp)
  missing_ts <- sum(is.na(ts_raw))
  ts <- parse_ts(ts_raw)
  invalid_ts <- sum(is.na(ts)) - missing_ts
  if (invalid_ts > 0) {
    errors <- sprintf("Found %d invalid unparseable timestamps.", invalid_ts)
    return(result("INVALID"))
  }
  if (missing_ts > 0) {
    errors <- sprintf("Found %d missing timestamps.", missing_ts)
    return(result("INVALID"))
  }

  dup <- sum(duplicated(ts))
  if (dup > 0) warnings <- c(warnings, sprintf("%d duplicate timestamps detected.", dup))

  ord <- order(ts)
  ts <- ts[ord]
  energy_raw <- df$energy_consumption[ord]
  start_ts <- fmt_ts(min(ts))
  end_ts <- fmt_ts(max(ts))
  duration_days <- as.numeric(difftime(max(ts), min(ts), units = "days"))

  energy <- suppressWarnings(as.numeric(as.character(energy_raw)))
  invalid_energy <- sum(is.na(energy)) - sum(is.na(energy_raw))
  if (invalid_energy > 0) {
    errors <- c(errors, sprintf("Found %d invalid non-numeric energy values.", invalid_energy))
  }
  negative <- sum(energy < 0, na.rm = TRUE)
  if (negative > 0) {
    errors <- c(errors, sprintf("Found %d negative energy consumption values.", negative))
  }
  if (length(errors) > 0) return(result("INVALID"))

  unique_ts <- sort(unique(ts))
  if (length(unique_ts) > 1) {
    diffs <- as.numeric(diff(unique_ts), units = "secs")
    counts <- table(diffs)
    common <- min(as.numeric(names(counts)[counts == max(counts)]))
    interval <- format_timedelta(common)
    interval_secs <- common
    consistency <- round(mean(diffs == common) * 100, 2)
    if (consistency < 100) {
      warnings <- c(warnings, sprintf("Sampling consistency is %s%%.", format(consistency)))
    }
    gaps <- sum(diffs > common)
    if (gaps > 0) warnings <- c(warnings, sprintf("%d timestamp gaps detected.", gaps))
  } else {
    interval <- "N/A"
  }

  if (duration_days < 7) {
    readiness <- "Insufficient history"
    warnings <- c(warnings, "Insufficient history for forecasting (less than 7 days).")
  } else if (duration_days < 30) {
    readiness <- "Basic"
  } else if (duration_days < 90) {
    readiness <- "Good"
  } else {
    readiness <- "Strong"
  }

  result(if (length(warnings) > 0) "VALID_WITH_WARNINGS" else "VALID")
}

# Persist a validated upload to Supabase Storage + table and the local cache.
store_upload <- function(bytes, filename, user_id, validation) {
  upload_id <- uuid::UUIDgenerate()
  storage_path <- paste0(user_id, "/", upload_id, "/", filename)
  sb_upload(storage_path, bytes, "text/csv")

  record <- list(
    id = upload_id,
    user_id = user_id,
    file_name = filename,
    storage_path = storage_path,
    file_type = "text/csv",
    file_size = length(bytes),
    record_count = validation$records,
    interval_minutes = if (is.null(validation$interval_seconds)) 60L else as.integer(round(validation$interval_seconds / 60)),
    validation_status = validation$status,
    analysis_status = "PENDING"
  )
  # TIMESTAMPTZ columns reject empty values, so only send them when present.
  if (!is.null(validation$start_timestamp)) record$start_timestamp <- validation$start_timestamp
  if (!is.null(validation$end_timestamp)) record$end_timestamp <- validation$end_timestamp
  sb_insert("uploaded_datasets", record)

  writeBin(bytes, file.path(UPLOAD_DIR, paste0(upload_id, ".csv")))
  upload_id
}

validate_upload <- function(bytes, filename, user_id) {
  if (!grepl("\\.csv$", filename, ignore.case = TRUE)) {
    return(list(valid = FALSE, records = 0L, start_timestamp = NULL, end_timestamp = NULL, interval = NULL,
                warnings = list(), errors = list("File is not a CSV."),
                forecasting_readiness = NULL, upload_id = NULL))
  }
  tmp <- tempfile(fileext = ".csv")
  on.exit(unlink(tmp))
  writeBin(bytes, tmp)
  r <- validate_user_csv(tmp)
  valid <- r$status %in% c("VALID", "VALID_WITH_WARNINGS")
  upload_id <- if (valid) store_upload(bytes, filename, user_id, r)
  list(valid = valid, records = r$records, start_timestamp = r$start_timestamp,
       end_timestamp = r$end_timestamp, interval = r$detected_interval, warnings = r$warnings,
       errors = r$errors, forecasting_readiness = r$forecasting_readiness, upload_id = upload_id)
}
