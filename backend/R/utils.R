# Shared config, error classes and time helpers for the EnergySense R backend.

`%||%` <- function(a, b) if (is.null(a)) b else a

ROOT <- Sys.getenv("PROJECT_ROOT", getwd())
METRICS <- file.path(ROOT, "results", "metrics")
ANALYTICS <- file.path(ROOT, "results", "analytics")
PREDICTIONS <- file.path(ROOT, "results", "predictions")
MODELS <- file.path(ROOT, "models", "final")

RATE_INR_PER_KWH <- 7.00
MIN_HOURLY_HISTORY <- 169L

UPLOAD_DIR <- file.path(tempdir(), "energy_uploads")
dir.create(UPLOAD_DIR, showWarnings = FALSE, recursive = TRUE)

# --- errors -----------------------------------------------------------------
# http_error -> mapped to a status code by the router's error handler.
# value_error / not_found_error -> domain errors, translated by the callers.
make_error <- function(class, message, ...) {
  stop(structure(class = c(class, "error", "condition"), list(message = message, call = NULL, ...)))
}
http_error <- function(status, detail) make_error("http_error", detail, status = status)
value_error <- function(message) make_error("value_error", message)
not_found_error <- function(message) make_error("not_found_error", message)

# --- time -------------------------------------------------------------------
# All timestamps are handled as timezone-naive wall-clock values, stored as UTC.
TS_ORDERS <- c("Ymd HMS", "Ymd HM", "Ymd", "mdY HMS", "mdY HM", "mdY", "dmY HMS", "dmY HM", "dmY")

parse_ts <- function(x) {
  lubridate::parse_date_time(as.character(x), orders = TS_ORDERS, tz = "UTC", quiet = TRUE)
}

fmt_ts <- function(x, sep = " ") format(x, paste0("%Y-%m-%d", sep, "%H:%M:%S"), tz = "UTC")

hour_of <- function(x) as.integer(format(x, "%H", tz = "UTC"))

# A JSON object that is empty (jsonlite would otherwise emit [] for list()).
empty_object <- function() structure(list(), names = character(0))

is_uuid_like <- function(x) is.character(x) && length(x) == 1 && grepl("^[A-Za-z0-9-]+$", x)
