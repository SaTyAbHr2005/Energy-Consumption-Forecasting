# Advanced leakage-free feature set for hourly energy forecasting.
# Used by BOTH model training (backend/pipeline) and the API, so the two can never drift apart.
# It reproduces build_features() from the original Python training script, including its quirks
# that the shipped models were trained with:
#   * only lags {1,2,3,4,6,8,12,18,24,36,48,72,96,120,144,168} exist, so prev_day_* use
#     lag_36/lag_48, same_hour_avg_14d equals the 7-day average, and only trend_1h/trend_3h exist;
#   * every rolling / EWM feature uses the series shifted by one hour (the target hour is excluded).

FEATURE_LAGS <- c(1, 2, 3, 4, 6, 8, 12, 18, 24, 36, 48, 72, 96, 120, 144, 168)

shift_by <- function(x, k) {
  n <- length(x)
  if (k >= n) return(rep(NA_real_, n))
  c(rep(NA_real_, k), x[seq_len(n - k)])
}

# Trailing-window statistics; a window containing any NA gives NA (pandas min_periods = window).
roll_stat <- function(x, w, fn) {
  switch(fn,
    mean = data.table::frollmean(x, w, align = "right", algo = "exact"),
    min = data.table::frollmin(x, w, align = "right", algo = "exact"),
    max = data.table::frollmax(x, w, align = "right", algo = "exact"),
    data.table::frollapply(x, w, get(fn), fill = NA_real_, align = "right")
  )
}

# pandas Series.ewm(span = span, adjust = False).mean(), including its handling of gaps
# (the old value keeps decaying across missing observations).
ewm_mean <- function(x, span) {
  alpha <- 2 / (span + 1)
  n <- length(x)
  out <- numeric(n)
  avg <- x[1]
  old_wt <- 1
  out[1] <- avg
  for (i in seq_len(n)[-1]) {
    cur <- x[i]
    observed <- !is.na(cur)
    if (!is.na(avg)) {
      old_wt <- old_wt * (1 - alpha)
      if (observed) {
        if (avg != cur) avg <- (old_wt * avg + alpha * cur) / (old_wt + alpha)
        old_wt <- 1
      }
    } else if (observed) {
      avg <- cur
    }
    out[i] <- avg
  }
  out
}

# raw: data.frame(timestamp <POSIXct>, energy_kwh <numeric>). Returns raw plus one column per feature.
# The last row may have energy_kwh = NA (a future hour to predict): its features only use the past.
build_features <- function(raw, p90) {
  df <- raw[order(raw$timestamp), c("timestamp", "energy_kwh")]
  rownames(df) <- NULL
  y <- df$energy_kwh
  ts <- df$timestamp

  hour <- hour_of(ts)
  dow <- lubridate::wday(ts, week_start = 1) - 1L # 0 = Monday
  month <- lubridate::month(ts)
  weekend <- as.integer(dow >= 5)
  df$hour <- hour
  df$dow <- dow
  df$month <- month
  df$quarter <- (month - 1L) %/% 3L + 1L
  df$is_weekend <- weekend
  for (nm in c("hour", "dow", "month")) {
    period <- c(hour = 24, dow = 7, month = 12)[[nm]]
    df[[paste0(nm, "_sin")]] <- sin(2 * pi * df[[nm]] / period)
    df[[paste0(nm, "_cos")]] <- cos(2 * pi * df[[nm]] / period)
  }
  df$hour_x_dow <- hour * dow
  df$hour_x_weekend <- hour * weekend
  df$month_x_hour <- month * hour
  df$dow_x_month <- dow * month

  for (lag in FEATURE_LAGS) df[[paste0("lag_", lag)]] <- shift_by(y, lag)

  yp <- shift_by(y, 1) # the "previous hour" series
  for (w in c(3, 6, 12, 24, 48, 72, 168)) df[[paste0("roll_mean_", w)]] <- roll_stat(yp, w, "mean")
  for (w in c(6, 12, 24, 48, 168)) df[[paste0("roll_std_", w)]] <- roll_stat(yp, w, "sd")
  for (w in c(24, 168)) {
    df[[paste0("roll_min_", w)]] <- roll_stat(yp, w, "min")
    df[[paste0("roll_max_", w)]] <- roll_stat(yp, w, "max")
    df[[paste0("roll_median_", w)]] <- roll_stat(yp, w, "median")
  }
  for (span in c(3, 6, 12, 24, 48)) df[[paste0("ewm_", span)]] <- ewm_mean(yp, span)

  df$trend_1h <- df$lag_1 - df$lag_2
  df$trend_3h <- df$lag_1 - df$lag_4

  same_hour <- rowMeans(df[paste0("lag_", seq(24, 168, by = 24))])
  df$same_hour_avg_7d <- same_hour
  df$same_hour_avg_14d <- same_hour
  prev_day <- as.matrix(df[c("lag_36", "lag_48")])
  df$prev_day_total <- rowSums(prev_day)
  df$prev_day_mean <- rowMeans(prev_day)
  df$prev_day_max <- do.call(pmax, as.data.frame(prev_day))
  df$prev_day_min <- do.call(pmin, as.data.frame(prev_day))
  df$prev_week_same_hour <- df$lag_168
  df$prev_week_same_hour_avg <- df$lag_168
  df$is_peak_prev_hour <- as.integer(df$lag_1 >= p90)
  df
}

feature_columns <- function(df) setdiff(names(df), c("timestamp", "energy_kwh"))
