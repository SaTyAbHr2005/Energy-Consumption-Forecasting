# EnergySense API (R / plumber). Build from the project root:
#   docker build -t energysense-api .
FROM rocker/r-ver:4.5.1

RUN apt-get update && apt-get install -y --no-install-recommends \
      libcurl4-openssl-dev libssl-dev libsodium-dev zlib1g-dev \
      libtesseract-dev libleptonica-dev tesseract-ocr-eng tesseract-ocr-mar libmagick++-dev \
    && rm -rf /var/lib/apt/lists/*

# Posit Package Manager serves prebuilt Linux binaries (fast install).
RUN Rscript -e 'options(repos = c(CRAN = "https://packagemanager.posit.co/cran/__linux__/noble/latest")); \
    install.packages(c("plumber", "httr2", "jsonlite", "xgboost", "lubridate", "uuid", "data.table", "tesseract", "magick"))'

# Tesseract's OpenMP threads thrash on Render's fractional free-tier CPU (~3x slower); one thread is fastest there.
ENV OMP_THREAD_LIMIT=1

WORKDIR /app
COPY backend/ backend/
COPY models/final/ models/final/
COPY results/ results/

# Render injects PORT; run.R reads it (default 8000).
EXPOSE 8000
CMD ["Rscript", "backend/run.R"]
