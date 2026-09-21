# HTTP layer: plumber router exposing the same API the Next.js frontend already uses.

BOOT_ID <- uuid::UUIDgenerate() # changes on every restart; SessionManager.tsx logs users out when it does

allowed_origins <- function() {
  c("http://localhost:3000", "http://127.0.0.1:3000", "http://localhost:3001", "http://127.0.0.1:3001",
    Sys.getenv("FRONTEND_URL"))
}

cors_filter <- function(req, res) {
  origin <- req$HTTP_ORIGIN
  if (!is.null(origin) && origin %in% allowed_origins()) {
    res$setHeader("Access-Control-Allow-Origin", origin)
    res$setHeader("Access-Control-Allow-Credentials", "true")
    res$setHeader("Vary", "Origin")
  }
  if (identical(req$REQUEST_METHOD, "OPTIONS")) {
    res$setHeader("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
    res$setHeader("Access-Control-Allow-Headers", req$HTTP_ACCESS_CONTROL_REQUEST_HEADERS %||% "*")
    res$status <- 200L
    return(list())
  }
  plumber::forward()
}

# Same error shape as the old FastAPI backend: {"detail": "..."}.
error_handler <- function(req, res, err) {
  status <- if (inherits(err, "http_error")) err$status else 500L
  res$status <- status
  if (status >= 500) message("ERROR ", req$REQUEST_METHOD, " ", req$PATH_INFO, ": ", conditionMessage(err))
  list(detail = if (status >= 500) "Internal server error" else conditionMessage(err))
}

not_found_handler <- function(req, res) {
  res$status <- 404L
  list(detail = "Not Found")
}

# Returns the authenticated user's id or raises 401/403.
current_user <- function(req) {
  header <- req$HTTP_AUTHORIZATION
  if (is.null(header) || !grepl("^Bearer +", header, ignore.case = TRUE)) http_error(403, "Not authenticated")
  id <- tryCatch(sb_get_user_id(sub("^Bearer +", "", header, ignore.case = TRUE)), error = function(e) NULL)
  if (is.null(id)) http_error(401, "Invalid authentication credentials")
  id
}

# The uploaded file part of a multipart/form-data request.
uploaded_file <- function(req) {
  part <- req$body$file
  if (is.null(part)) http_error(422, "Field required: file")
  bytes <- part$value
  if (is.character(bytes)) bytes <- charToRaw(paste(bytes, collapse = "\n"))
  list(bytes = bytes, filename = part$filename %||% "upload", content_type = part$content_type %||% "application/octet-stream")
}

param_or_null <- function(x) if (is.null(x) || !nzchar(x)) NULL else x

build_api <- function() {
  plumber::pr() |>
    plumber::pr_set_serializer(plumber::serializer_json(auto_unbox = TRUE, na = "null", null = "null", digits = NA)) |>
    plumber::pr_set_error(error_handler) |>
    plumber::pr_set_404(not_found_handler) |>
    plumber::pr_filter("cors", cors_filter) |>

    # --- health ---
    plumber::pr_get("/", function() list(service = "energy-forecasting-api", mode = "historical forecast simulation")) |>
    plumber::pr_get("/health", function() list(status = "healthy", service = "energy-forecasting-api")) |>
    plumber::pr_get("/api/health", function() list(status = "healthy", service = "energy-forecasting-api", boot_id = BOOT_ID)) |>

    # --- bills ---
    plumber::pr_post("/api/upload/bill", function(req) {
      uid <- current_user(req)
      file <- uploaded_file(req)
      bill_id <- uuid::UUIDgenerate()
      ext <- if (grepl(".", file$filename, fixed = TRUE)) tail(strsplit(file$filename, ".", fixed = TRUE)[[1]], 1) else "jpg"
      storage_path <- sprintf("%s/bills/%s.%s", uid, bill_id, ext)
      try(sb_upload(storage_path, file$bytes, file$content_type), silent = TRUE)

      # Demo OCR: fixed values from a sample MSEDCL bill. A real system would call an
      # OCR service (Google Cloud Vision / AWS Textract) on the uploaded image.
      cost <- 1330.00
      consumption <- 138.0
      bill_date <- "August 2026"
      if (length(sb_select("user_bills", list(user_id = paste0("eq.", uid), bill_date = paste0("eq.", bill_date)), select = "id")) > 0) {
        http_error(409, sprintf("A bill for %s has already been uploaded.", bill_date))
      }
      sb_insert("user_bills", list(user_id = uid, bill_date = bill_date, cost = cost, consumption = consumption,
                                   storage_path = storage_path, created_at = format(Sys.time(), "%Y-%m-%dT%H:%M:%S", tz = "UTC")))
      list(bill_id = bill_id, storage_path = storage_path, extracted_cost = cost,
           extracted_consumption = consumption, extracted_date = bill_date,
           message = "Bill uploaded and processed successfully.")
    }) |>
    plumber::pr_get("/api/bills", function(req) {
      sb_select("user_bills", list(user_id = paste0("eq.", current_user(req))),
                select = "id,bill_date,cost,consumption,storage_path,created_at", order = "created_at.desc")
    }) |>
    plumber::pr_delete("/api/bills/<bill_id:int>", function(req, bill_id) {
      deleted <- sb_delete("user_bills", list(id = paste0("eq.", bill_id), user_id = paste0("eq.", current_user(req))))
      if (length(deleted) == 0) http_error(404, "Bill not found")
      list(success = TRUE)
    }) |>

    # --- datasets ---
    plumber::pr_post("/api/upload", function(req) {
      uid <- current_user(req)
      file <- uploaded_file(req)
      validate_upload(file$bytes, file$filename, uid)
    }) |>
    plumber::pr_get("/api/datasets", function(req) {
      sb_select("uploaded_datasets", list(user_id = paste0("eq.", current_user(req))), order = "created_at.desc")
    }) |>
    plumber::pr_delete("/api/datasets/<dataset_id>", function(req, dataset_id) {
      uid <- current_user(req)
      row <- if (is_uuid_like(dataset_id)) sb_select("uploaded_datasets", list(id = paste0("eq.", dataset_id)), select = "user_id,storage_path")
      if (length(row) == 0 || row[[1]]$user_id != uid) http_error(404, "Dataset not found or permission denied")
      sb_delete("uploaded_datasets", list(id = paste0("eq.", dataset_id)))
      if (!is.null(row[[1]]$storage_path)) try(sb_remove(row[[1]]$storage_path), silent = TRUE)
      unlink(file.path(UPLOAD_DIR, paste0(dataset_id, ".csv")))
      list(success = TRUE)
    }) |>

    # --- per-user forecast and dashboard ---
    plumber::pr_post("/api/forecast/user", function(req, horizon = "1", upload_id = NULL) {
      uid <- current_user(req)
      # Catch first, raise outside: an error raised inside a tryCatch handler would be
      # caught by the generic `error` handler of the same call.
      result <- tryCatch(
        smart_grid_analysis(generate_forecast(param_or_null(upload_id), suppressWarnings(as.integer(horizon)), uid)),
        error = function(e) e
      )
      if (inherits(result, "not_found_error")) http_error(404, conditionMessage(result))
      if (inherits(result, "value_error")) http_error(422, conditionMessage(result))
      if (inherits(result, "error")) {
        message("Forecast failed: ", conditionMessage(result))
        http_error(500, "We couldn't generate the forecast.")
      }
      result
    }) |>
    plumber::pr_get("/api/user/periods", function(req) get_user_periods(current_user(req))) |>
    plumber::pr_get("/api/user/dashboard", function(req, period = NULL) {
      user_dashboard(current_user(req), param_or_null(period))
    }) |>
    plumber::pr_get("/api/user/analytics/cost", function(req) user_cost_analytics(current_user(req))) |>

    # --- pre-computed project results (public) ---
    plumber::pr_get("/api/forecast", function(horizon = "1") {
      h <- suppressWarnings(as.integer(horizon))
      if (!(h %in% c(1L, 24L))) http_error(400, "horizon must be 1 or 24")
      list(model = "XGBoost", horizon = h, forecast = artifact_forecast(h))
    }) |>
    plumber::pr_get("/api/analytics/summary", function() list(historical = artifact_insights(), forecast = artifact_summary())) |>
    plumber::pr_get("/api/analytics/hourly", function() read_records(ANALYTICS, "hourly_profile.csv", 24L)) |>
    plumber::pr_get("/api/analytics/daily", function() read_records(ANALYTICS, "daily_consumption.csv")) |>
    plumber::pr_get("/api/analytics/weekday", function() read_records(ANALYTICS, "weekday_profile.csv", 7L)) |>
    plumber::pr_get("/api/smart-grid/summary", function() artifact_summary()) |>
    plumber::pr_get("/api/smart-grid/peaks", function() read_records(METRICS, "peak_demand_forecast.csv")) |>
    plumber::pr_get("/api/smart-grid/tou", function() artifact_tou()) |>
    plumber::pr_get("/api/smart-grid/load-shifting", function() read_records(METRICS, "load_shift_recommendations.csv")) |>
    plumber::pr_get("/api/smart-grid/sensitivity", function() read_records(METRICS, "load_shift_sensitivity.csv")) |>
    plumber::pr_get("/api/smart-grid/recommendations", function() list(recommendations = artifact_recommendations())) |>
    plumber::pr_get("/api/recommendations", function() list(recommendations = artifact_recommendations()))
}
