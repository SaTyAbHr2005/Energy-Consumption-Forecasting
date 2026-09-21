# Electricity-bill OCR (tesseract) tuned for MSEDCL / Mahavitaran bills (Marathi + English).
# Extracts: bill month, amount payable (Rs) and units consumed (kWh).

BILL_MONTH_NAMES <- c("January", "February", "March", "April", "May", "June", "July",
                      "August", "September", "October", "November", "December")

# Marathi / English month tokens as OCR tends to produce them (prefix match, OCR-typo tolerant).
BILL_MONTH_PATTERNS <- c(
  "^(जाने|नेवार|jan)", "^(फे|feb)", "^(मार|mar)", "^(एप|apr)", "^(मे$|may)", "^(जून|jun)",
  "^(जुल|jul)", "^(ऑग|आग|aug)", "^(सप्|sep)", "^(ऑक्|आक्|oct)", "^(नो|nov)", "^(डिस|dec)"
)

month_index <- function(token) {
  hit <- which(vapply(BILL_MONTH_PATTERNS, function(p) grepl(p, tolower(token), perl = TRUE), logical(1)))
  if (length(hit) == 1) unname(hit) else NA_integer_
}

# All "<month word> [-] <year> [number]" occurrences in `text`.
month_year_matches <- function(text) {
  re <- "([\\p{L}\\p{M}]{2,15})\\s*[-–—]?\\s*(20[0-9]{2})(?:\\s+([0-9]{1,5})(?![0-9.]))?"
  m <- gregexpr(re, text, perl = TRUE)[[1]]
  if (m[1] == -1) return(list())
  starts <- attr(m, "capture.start"); lens <- attr(m, "capture.length")
  lapply(seq_along(m), function(i) {
    part <- function(k) if (lens[i, k] > 0) substr(text, starts[i, k], starts[i, k] + lens[i, k] - 1) else NA_character_
    list(month = month_index(part(1)), year = as.integer(part(2)), units = suppressWarnings(as.numeric(part(3))))
  })
}

# Bill month: "BILL OF SUPPLY FOR THE MONTH OF - <month>-<year>", else the first dd-mm-yyyy date.
parse_bill_month <- function(text) {
  pos <- regexpr("MONTH\\s*OF", text, ignore.case = TRUE, perl = TRUE)
  if (pos[1] > 0) {
    tail_txt <- substr(text, pos[1], pos[1] + 90)
    for (m in month_year_matches(tail_txt)) if (!is.na(m$month)) return(list(month = m$month, year = m$year))
  }
  d <- regmatches(text, regexec("([0-9]{1,2})[-/.]([0-9]{2})[-/.](20[0-9]{2})", text, perl = TRUE))[[1]]
  if (length(d) == 4 && as.integer(d[3]) %in% 1:12) return(list(month = as.integer(d[3]), year = as.integer(d[4])))
  NULL
}

# Amount payable: the "देयक रक्कम रु" box; fallbacks: first amount after the bill date, then the median "Rs." amount.
parse_bill_cost <- function(text) {
  m <- regmatches(text, regexec("देयक\\s+र\\S*\\s+र\\S*[\\s:;|]*([0-9]{2,7}[.,][0-9]{2})", text, perl = TRUE))[[1]]
  if (length(m) == 2) return(as.numeric(sub(",", ".", m[2])))
  # label garbled by OCR: the first amount printed after the bill date is the payable amount
  near <- regmatches(text, regexec("[0-9]{1,2}[-/.][0-9]{2}[-/.]20[0-9]{2}[\\s\\S]{0,500}?([0-9]{2,7}[.,][0-9]{2})(?![0-9])", text, perl = TRUE))[[1]]
  if (length(near) == 2) return(as.numeric(sub(",", ".", near[2])))
  rs <- regmatches(text, gregexpr("Rs\\.?\\s*([0-9]{2,7}[.,][0-9]{2})", text, perl = TRUE))[[1]]
  if (length(rs)) return(stats::median(as.numeric(sub(",", ".", sub("^Rs\\.?\\s*", "", rs)))))
  NA_real_
}

# Units: the "वीज वापर" (consumption history) line for the bill month; fallback = meter row
# "<previous reading> <multiplier 1.00> <units> <adjusted> <total>" where units + adjusted = total.
parse_bill_units <- function(text, bill) {
  for (m in month_year_matches(text)) {
    if (identical(m$month, bill$month) && identical(m$year, bill$year) && !is.na(m$units)) return(m$units)
  }
  row <- regmatches(text, gregexpr("[0-9]+\\s+[0-9]+[.,][0-9]{2}\\s+([0-9]{1,5})\\s+([0-9]{1,5}|[oO°])\\s+([0-9]{1,5})", text, perl = TRUE))[[1]]
  for (r in row) {
    n <- suppressWarnings(as.numeric(strsplit(gsub("[oO°]", "0", r), "\\s+")[[1]]))
    k <- length(n)
    if (k >= 5 && n[k - 2] + n[k - 1] == n[k]) return(n[k])
  }
  NA_real_
}

# Adani Electricity (Mumbai) layout: a summary row "Bill Month | Units Consumed | Current Month Bill | ..."
# ("AUG-26  145  1283.54 ...") and the payable amount as a round sum ("₹1270.00") just after it.
ADANI_MONTHS <- c("JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC")

parse_adani_text <- function(text) {
  pos <- regexpr("Bill\\s*Month", text, ignore.case = TRUE, perl = TRUE)
  tail_txt <- substr(text, max(pos[1], 1), max(pos[1], 1) + 700)
  re <- paste0("\\b(", paste(ADANI_MONTHS, collapse = "|"), ")[A-Z]*\\s*[-–]?\\s*([0-9]{2})(?![0-9])")
  m <- regexec(re, tail_txt, ignore.case = TRUE, perl = TRUE)
  hit <- regmatches(tail_txt, m)[[1]]
  if (length(hit) != 3) return(NULL)
  month <- match(toupper(hit[2]), ADANI_MONTHS)
  year <- 2000L + as.integer(hit[3])
  after <- substring(tail_txt, regexpr(hit[1], tail_txt, fixed = TRUE)[1] + nchar(hit[1]))
  units <- regmatches(after, regexec("^\\s*([0-9]{1,5})(?![0-9.])", after, perl = TRUE))[[1]]
  # payable amount: first round-sum "NNNN.00" after the row (the leading rupee sign is often OCR'd as a 7)
  amt <- regmatches(after, regexec("([0-9]{3,6})\\.00(?![0-9])", after, perl = TRUE))[[1]]
  cost <- NA_real_
  if (length(amt) == 2) {
    cost <- as.numeric(amt[2])
    if (cost >= 10000 && startsWith(amt[2], "7")) cost <- as.numeric(substring(amt[2], 2))
  }
  if (is.na(cost)) {
    tot <- regmatches(text, regexec("Total\\s+current\\s+month\\s+charges[^0-9]*([0-9]{3,6}\\.[0-9]{2})", text, ignore.case = TRUE, perl = TRUE))[[1]]
    if (length(tot) == 2) cost <- as.numeric(tot[2])
  }
  list(month = month, year = year, cost = cost, consumption = if (length(units) == 2) as.numeric(units[2]) else NA_real_)
}

parse_bill_text <- function(text) {
  if (grepl("Units\\s*Consumed", text, ignore.case = TRUE, perl = TRUE)) {
    a <- parse_adani_text(text)
    if (!is.null(a)) {
      return(list(month = a$month, year = a$year, bill_date = sprintf("%s %d", BILL_MONTH_NAMES[a$month], a$year),
                  cost = a$cost, consumption = a$consumption))
    }
  }
  bill <- parse_bill_month(text)
  list(
    month = bill$month, year = bill$year,
    bill_date = if (!is.null(bill)) sprintf("%s %d", BILL_MONTH_NAMES[bill$month], bill$year) else NA_character_,
    cost = parse_bill_cost(text),
    consumption = if (!is.null(bill)) parse_bill_units(text, bill) else NA_real_
  )
}

# Grayscale + upscale + normalise, then OCR. psm 11 (sparse text) reads the boxed fields best;
# psm 6 keeps table rows on one line (used only when the first pass misses the units).
bill_ocr_text <- function(image_path, psm = 11) {
  img <- magick::image_read(image_path) |>
    magick::image_convert(colorspace = "gray") |>
    magick::image_resize("2000x") |>
    magick::image_normalize()
  tmp <- tempfile(fileext = ".png")
  on.exit(unlink(tmp))
  magick::image_write(img, tmp)
  tesseract::ocr(tmp, engine = tesseract::tesseract("eng+mar", options = list(tessedit_pageseg_mode = psm)))
}

extract_bill_fields <- function(image_path) {
  text <- bill_ocr_text(image_path, 11)
  out <- parse_bill_text(text)
  if (is.na(out$consumption) && !is.na(out$bill_date)) {
    out2 <- parse_bill_text(paste(text, bill_ocr_text(image_path, 6), sep = "\n"))
    if (!is.na(out2$consumption)) out <- out2
  }
  out
}
