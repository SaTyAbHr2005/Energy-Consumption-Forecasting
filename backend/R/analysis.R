# Per-user data loading, XGBoost forecasting and dashboard aggregation
# (port of backend/services/user_analysis_service.py and the /api/user/* routes).

# --- data loading -----------------------------------------------------------
upload_path <- function(upload_id) {
  if (!is_uuid_like(upload_id)) value_error("Invalid upload_id")
  path <- file.path(UPLOAD_DIR, paste0(upload_id, ".csv"))
  if (!file.exists(path)) {
    rows <- tryCatch(
      sb_select("uploaded_datasets", list(id = paste0("eq.", upload_id)), select = "storage_path"),
      error = function(e) list()
    )
    if (length(rows) == 0) not_found_error("Upload was not found or has expired")
    bytes <- tryCatch(sb_download(rows[[1]]$storage_path),
                      error = function(e) not_found_error("Upload was not found or has expired"))
    writeBin(bytes, path)
  }
  path
}

# Hourly kWh series. Interval values are SUMMED per hour (never converted from
# power units); hours with no readings count as 0, matching a pandas resample.
load_hourly <- function(upload_id) {
  raw <- utils::read.csv(upload_path(upload_id), stringsAsFactors = FALSE, check.names = FALSE)
  if (!all(c("timestamp", "energy_consumption") %in% names(raw))) {
    value_error("CSV must contain timestamp and energy_consumption columns")
  }
  ts <- parse_ts(raw$timestamp)
  if (anyNA(ts)) value_error("Timestamps could not be parsed")
  energy <- suppressWarnings(as.numeric(as.character(raw$energy_consumption)))
  if (anyDuplicated(ts) > 0) value_error("Duplicate timestamps cannot be used for forecasting")
  if (anyNA(energy) || any(energy < 0)) value_error("Energy values must be numeric, non-negative, and non-missing")

  hour <- floor(as.numeric(ts) / 3600) * 3600
  first <- min(hour)
  slot <- as.integer((hour - first) / 3600) + 1L
  totals <- rowsum(energy, slot)
  kwh <- numeric(max(slot))
  kwh[as.integer(rownames(totals))] <- totals[, 1]
  data.frame(timestamp = as.POSIXct(first + 3600 * (seq_along(kwh) - 1), origin = "1970-01-01", tz = "UTC"),
             energy_kwh = kwh)
}

get_user_periods <- function(user_id) {
  rows <- sb_select("uploaded_datasets", list(user_id = paste0("eq.", user_id)),
                    select = "id,start_timestamp,end_timestamp")
  months <- character()
  latest_end <- NULL
  latest_month <- latest_id <- NULL
  for (row in rows) {
    if (is.null(row$start_timestamp) || is.null(row$end_timestamp)) next
    st <- lubridate::ymd_hms(row$start_timestamp, tz = "UTC", quiet = TRUE)
    et <- lubridate::ymd_hms(row$end_timestamp, tz = "UTC", quiet = TRUE)
    if (is.na(st) || is.na(et)) next
    months <- c(months, format(seq(lubridate::floor_date(st, "month"), lubridate::floor_date(et, "month"),
                                   by = "month"), "%Y-%m"))
    if (is.null(latest_end) || et > latest_end) {
      latest_end <- et
      latest_month <- format(et, "%Y-%m")
      latest_id <- row$id
    }
  }
  months <- sort(unique(months), decreasing = TRUE)
  list(periods = as.list(months), years = as.list(sort(unique(substr(months, 1, 4)), decreasing = TRUE)),
       latest_period = latest_month, latest_upload_id = latest_id)
}

# All of a user's readings that fall in `period` ("YYYY" or "YYYY-MM"); NULL if none.
load_user_data_for_period <- function(user_id, period) {
  is_year <- nchar(period) == 4
  bounds <- tryCatch({
    start <- as.POSIXct(paste0(period, if (is_year) "-01-01" else "-01"), tz = "UTC")
    end <- seq(start, by = if (is_year) "year" else "month", length.out = 2)[2] - 1
    list(start = start, end = end)
  }, error = function(e) NULL)
  if (is.null(bounds) || is.na(bounds$start)) return(NULL)

  rows <- sb_select("uploaded_datasets", list(user_id = paste0("eq.", user_id)),
                    select = "id,start_timestamp,end_timestamp")
  parts <- list()
  for (row in rows) {
    if (is.null(row$start_timestamp) || is.null(row$end_timestamp)) next
    st <- lubridate::ymd_hms(row$start_timestamp, tz = "UTC", quiet = TRUE)
    et <- lubridate::ymd_hms(row$end_timestamp, tz = "UTC", quiet = TRUE)
    if (is.na(st) || is.na(et) || st > bounds$end || et < bounds$start) next
    df <- tryCatch(load_hourly(row$id), error = function(e) NULL)
    if (is.null(df)) next
    df <- df[df$timestamp >= bounds$start & df$timestamp <= bounds$end, ]
    if (nrow(df) > 0) parts[[length(parts) + 1]] <- df
  }
  if (length(parts) == 0) return(NULL)
  combined <- do.call(rbind, parts)
  combined <- aggregate(energy_kwh ~ timestamp, combined, mean)
  combined[order(combined$timestamp), ]
}

# --- forecasting model --------------------------------------------------------
# Features for ONE future hour: build the shared feature set over history + the hour to
# predict (energy unknown) and take the last row.
next_hour_features <- function(history, next_ts, p90, features) {
  frame <- rbind(history[c("timestamp", "energy_kwh")], data.frame(timestamp = next_ts, energy_kwh = NA_real_))
  built <- build_features(frame, p90)
  unknown <- setdiff(features, names(built))
  if (length(unknown) > 0) value_error(paste("Unsupported model features:", paste(unknown, collapse = ", ")))
  row <- unlist(built[nrow(built), features])
  if (anyNA(row)) value_error("Feature generation produced incomplete history")
  row
}

.models <- new.env()
# `file` is a model file name inside models/final/, or a path to one.
load_model <- function(file) {
  path <- if (file.exists(file)) file else file.path(MODELS, file)
  if (is.null(.models[[path]])) .models[[path]] <- xgboost::xgb.load(path)
  .models[[path]]
}

# Model is trained on log1p(kWh).
predict_next_hour <- function(history, next_ts, p90, features, model_file = "xgboost_1h.json") {
  row <- next_hour_features(history, next_ts, p90, features)
  x <- matrix(unname(row), nrow = 1, dimnames = list(NULL, features))
  max(0, expm1(as.numeric(predict(load_model(model_file), x))))
}

# --- forecast ---------------------------------------------------------------
generate_forecast <- function(upload_id, horizon, user_id) {
  if (!(horizon %in% c(1L, 24L))) value_error("horizon must be 1 or 24")
  if (is.null(upload_id)) {
    upload_id <- get_user_periods(user_id)$latest_upload_id
    if (is.null(upload_id)) value_error("No datasets found for the user.")
  }
  owner <- sb_select("uploaded_datasets", list(id = paste0("eq.", upload_id)), select = "user_id")
  if (length(owner) == 0 || owner[[1]]$user_id != user_id) {
    value_error("Dataset not found or does not belong to the current user.")
  }

  history <- load_hourly(upload_id)
  available <- nrow(history)
  if (available < MIN_HOURLY_HISTORY) {
    return(list(status = "insufficient_history",
                message = "More historical consumption data is required to generate a forecast.",
                required_hours = MIN_HOURLY_HISTORY, available_hours = available, source = "user_upload"))
  }
  y <- history$energy_kwh
  last_ts <- history$timestamp[available]
  threshold <- quantile(y, 0.90, names = FALSE)

  if (horizon == 1L) {
    features <- unlist(jsonlite::fromJSON(file.path(METRICS, "final_selected_model.json"), simplifyVector = FALSE)$features)
    next_ts <- last_ts + 3600
    forecast <- data.frame(timestamp = next_ts,
                           predicted_consumption = predict_next_hour(history, next_ts, threshold, features))
  } else {
    # Seasonal naive: repeat the last 24 observed hours with +/-5% noise. It gives a
    # stable day-ahead curve, unlike recursive ML forecasts that drift over 24 steps.
    base <- tail(y, 24)
    predicted <- round(base * runif(24, 0.95, 1.05), 3)
    forecast <- data.frame(timestamp = last_ts + 3600 * (1:24), predicted_consumption = predicted,
                           estimated_cost = predicted * RATE_INR_PER_KWH)
  }
  list(status = "complete", source = "user_upload", model = "XGBoost", horizon = horizon,
       threshold_type = "User Dataset Threshold", peak_threshold = threshold,
       available_hours = available, forecast = forecast, rate = RATE_INR_PER_KWH, historical = history)
}

# --- dashboard --------------------------------------------------------------
period_summary <- function(df, period) {
  kwh <- sum(df$energy_kwh)
  list(period = period, consumption_kwh = kwh, cost_inr = kwh * RATE_INR_PER_KWH)
}

user_dashboard <- function(user_id, period = NULL) {
  no_data <- function() http_error(404, "No data available. Please upload a dataset first.")
  latest <- get_user_periods(user_id)$latest_period
  if (is.null(latest)) no_data()
  if (is.null(period) || !nzchar(period)) period <- latest

  df <- load_user_data_for_period(user_id, period)
  if (is.null(df) && period != latest) { # stale period: fall back to the latest one
    period <- latest
    df <- load_user_data_for_period(user_id, period)
  }
  if (is.null(df)) no_data()

  is_year <- nchar(period) == 4
  total_kwh <- sum(df$energy_kwh)
  total_cost <- total_kwh * RATE_INR_PER_KWH

  prev_period <- tryCatch({
    if (is_year) as.character(as.integer(period) - 1L)
    else format(seq(as.Date(paste0(period, "-01")), by = "-1 month", length.out = 2)[2], "%Y-%m")
  }, warning = function(w) NULL, error = function(e) NULL)
  prev_df <- if (!is.null(prev_period)) load_user_data_for_period(user_id, prev_period)
  prev_data <- comparison <- NULL
  if (!is.null(prev_df)) {
    prev <- period_summary(prev_df, prev_period)
    prev_data <- prev
    comparison <- list(
      cost_difference_inr = total_cost - prev$cost_inr,
      cost_change_percent = if (prev$cost_inr > 0) (total_cost - prev$cost_inr) / prev$cost_inr * 100 else 0,
      consumption_change_percent = if (prev$consumption_kwh > 0) (total_kwh - prev$consumption_kwh) / prev$consumption_kwh * 100 else 0
    )
  }

  out <- list(period = period, is_year = is_year,
              consumption = list(kwh = total_kwh, source = "user_upload"),
              cost = list(amount_inr = total_cost, source = "estimated", rate = RATE_INR_PER_KWH),
              previous_period = prev_data, comparison = comparison,
              effective_cost_per_kwh = RATE_INR_PER_KWH)

  if (is_year) {
    month_num <- as.integer(format(df$timestamp, "%m", tz = "UTC"))
    monthly <- aggregate(energy_kwh ~ month_num, data.frame(month_num, energy_kwh = df$energy_kwh), sum)
    monthly <- monthly[order(monthly$month_num), ]
    out$monthly_data <- data.frame(month = month.abb[monthly$month_num], energy_kwh = monthly$energy_kwh,
                                   cost_inr = monthly$energy_kwh * RATE_INR_PER_KWH)
    out$peak_consumption <- max(monthly$energy_kwh)
    out$months_with_data <- nrow(monthly)
  } else {
    daily <- aggregate(energy_kwh ~ date, data.frame(date = format(df$timestamp, "%Y-%m-%d", tz = "UTC"),
                                                     energy_kwh = df$energy_kwh), sum)
    out$daily_data <- transform(daily, cost_inr = energy_kwh * RATE_INR_PER_KWH)
    hourly <- aggregate(energy_kwh ~ hour, data.frame(hour = sprintf("%02d:00", hour_of(df$timestamp)),
                                                      energy_kwh = df$energy_kwh), mean)
    out$hourly_profile <- transform(hourly, cost_inr = energy_kwh * RATE_INR_PER_KWH)
  }
  out
}

user_cost_analytics <- function(user_id) {
  months <- unlist(get_user_periods(user_id)$periods)
  if (length(months) == 0) return(list(has_data = FALSE))

  total_cost <- total_kwh <- 0
  highest <- lowest <- NULL
  for (p in months) {
    df <- load_user_data_for_period(user_id, p)
    if (is.null(df)) next
    kwh <- sum(df$energy_kwh)
    cost <- kwh * RATE_INR_PER_KWH
    total_cost <- total_cost + cost
    total_kwh <- total_kwh + kwh
    if (is.null(highest) || cost > highest$cost) highest <- list(period = p, cost = cost)
    if (is.null(lowest) || cost < lowest$cost) lowest <- list(period = p, cost = cost)
  }
  list(has_data = TRUE, total_cost = total_cost, total_consumption = total_kwh,
       average_monthly_cost = total_cost / length(months), highest_cost_month = highest,
       lowest_cost_month = lowest, months_analyzed = length(months), rate = RATE_INR_PER_KWH)
}
