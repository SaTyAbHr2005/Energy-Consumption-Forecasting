# Minimal Supabase client (Auth, PostgREST, Storage) over httr2.
# Uses the service-role key, so it must only ever run on the backend.

BUCKET <- "energy-csv"

sb_base <- function() sub("/+$", "", Sys.getenv("SUPABASE_URL"))
sb_key <- function() Sys.getenv("SUPABASE_SERVICE_ROLE_KEY")

sb_request <- function(path) {
  httr2::request(paste0(sb_base(), path)) |>
    httr2::req_headers(apikey = sb_key(), Authorization = paste("Bearer", sb_key())) |>
    httr2::req_error(is_error = function(resp) FALSE) |>
    httr2::req_timeout(30)
}

sb_check <- function(resp, what) {
  status <- httr2::resp_status(resp)
  if (status >= 400) {
    stop(sprintf("Supabase %s failed (%d): %s", what, status, httr2::resp_body_string(resp)), call. = FALSE)
  }
  resp
}

# --- auth -------------------------------------------------------------------
# Returns the user id for a valid access token, otherwise NULL.
sb_get_user_id <- function(token) {
  resp <- sb_request("/auth/v1/user") |>
    httr2::req_headers(Authorization = paste("Bearer", token)) |>
    httr2::req_perform()
  if (httr2::resp_status(resp) != 200) return(NULL)
  httr2::resp_body_json(resp)$id
}

# --- tables (PostgREST) -----------------------------------------------------
# `filters` is a named list such as list(user_id = "eq.<id>").
sb_select <- function(table, filters = list(), select = "*", order = NULL) {
  query <- c(list(select = select), filters, if (!is.null(order)) list(order = order))
  resp <- sb_request(paste0("/rest/v1/", table)) |>
    httr2::req_url_query(!!!query) |>
    httr2::req_perform()
  httr2::resp_body_json(sb_check(resp, paste("select from", table)))
}

sb_insert <- function(table, record) {
  sb_request(paste0("/rest/v1/", table)) |>
    httr2::req_headers(Prefer = "return=minimal") |>
    httr2::req_body_json(record, auto_unbox = TRUE) |>
    httr2::req_perform() |>
    sb_check(paste("insert into", table))
  invisible(TRUE)
}

# Returns the deleted rows, so callers can tell whether anything matched.
sb_delete <- function(table, filters) {
  resp <- sb_request(paste0("/rest/v1/", table)) |>
    httr2::req_method("DELETE") |>
    httr2::req_headers(Prefer = "return=representation") |>
    httr2::req_url_query(!!!filters) |>
    httr2::req_perform()
  httr2::resp_body_json(sb_check(resp, paste("delete from", table)))
}

# --- storage ----------------------------------------------------------------
encode_path <- function(path) {
  paste(vapply(strsplit(path, "/", fixed = TRUE)[[1]], utils::URLencode, "", reserved = TRUE), collapse = "/")
}

sb_upload <- function(path, bytes, content_type) {
  sb_request(paste0("/storage/v1/object/", BUCKET, "/", encode_path(path))) |>
    httr2::req_body_raw(bytes, type = content_type) |>
    httr2::req_perform() |>
    sb_check("storage upload")
  invisible(TRUE)
}

sb_download <- function(path) {
  resp <- sb_request(paste0("/storage/v1/object/authenticated/", BUCKET, "/", encode_path(path))) |>
    httr2::req_perform()
  httr2::resp_body_raw(sb_check(resp, "storage download"))
}

sb_remove <- function(paths) {
  sb_request(paste0("/storage/v1/object/", BUCKET)) |>
    httr2::req_method("DELETE") |>
    httr2::req_body_json(list(prefixes = as.list(paths)), auto_unbox = TRUE) |>
    httr2::req_perform() |>
    sb_check("storage remove")
  invisible(TRUE)
}
