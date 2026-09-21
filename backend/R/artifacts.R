# Read-only endpoints backed by the pre-computed files in results/
# (port of backend/services/artifact_service.py).

read_json <- function(dir, name) {
  path <- file.path(dir, name)
  if (!file.exists(path)) return(empty_object())
  jsonlite::fromJSON(path, simplifyVector = FALSE)
}

read_records <- function(dir, name, limit = 5000L) {
  path <- file.path(dir, name)
  if (!file.exists(path)) return(list())
  utils::read.csv(path, stringsAsFactors = FALSE, check.names = FALSE, nrows = limit)
}

artifact_summary <- function() read_json(METRICS, "smart_grid_summary.json")
artifact_insights <- function() read_json(METRICS, "energy_insights.json")
artifact_tou <- function() read_json(METRICS, "tou_summary.json")
artifact_recommendations <- function() artifact_summary()$recommendations %||% list()

artifact_forecast <- function(horizon) {
  path <- file.path(PREDICTIONS, "xgboost_predictions.csv")
  if (!file.exists(path)) return(list())
  frame <- utils::read.csv(path, stringsAsFactors = FALSE)
  frame <- frame[frame$horizon == horizon, ]
  data.frame(timestamp = frame$timestamp, predicted_consumption = frame$predicted)
}
