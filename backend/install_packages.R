# R package list for the backend (the R equivalent of requirements.txt).
#   Rscript backend/install_packages.R           # API only (what Render installs)
#   Rscript backend/install_packages.R pipeline  # API + Spark/ML pipeline + tests
api      <- c("plumber", "httr2", "jsonlite", "xgboost", "lubridate", "uuid", "data.table")
pipeline <- c("sparklyr", "dplyr", "arrow", "ranger", "ggplot2", "testthat")

pkgs <- if ("pipeline" %in% commandArgs(TRUE)) c(api, pipeline) else api
missing <- setdiff(pkgs, rownames(installed.packages()))
if (length(missing)) install.packages(missing, repos = "https://cloud.r-project.org")
if ("pipeline" %in% commandArgs(TRUE)) sparklyr::spark_install("3.5")  # needs Java 8/11/17
