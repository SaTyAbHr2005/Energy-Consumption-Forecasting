# Entry point. Run from the project root:  Rscript backend/run.R
# Reads SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY (from the environment or a .env file),
# optional FRONTEND_URL (extra CORS origin) and PORT (default 8000).

if (file.exists(".env")) readRenviron(".env")

for (f in list.files("backend/R", pattern = "\\.R$", full.names = TRUE)) source(f)

if (!nzchar(Sys.getenv("SUPABASE_URL")) || !nzchar(Sys.getenv("SUPABASE_SERVICE_ROLE_KEY"))) {
  stop("Missing Supabase configuration in environment (SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY).")
}

port <- as.integer(Sys.getenv("PORT", "8000"))
plumber::pr_run(build_api(), host = "0.0.0.0", port = port, docs = FALSE)
