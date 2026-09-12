# User CSV Format Specification

## Purpose
The system allows homeowners to upload their own household electricity consumption data via a CSV file. This data is validated, processed, and used to provide personalized energy insights and forecasting using our machine learning models.

## Required Columns
The uploaded CSV must contain the following required columns:
- `timestamp`
- `energy_consumption`

Extra columns (e.g., `temperature`, `humidity`) are allowed and will not cause validation to fail, but they may be ignored by the forecasting engine unless explicitly supported.

## Units & Interpretation
- **`timestamp`**: The date and time of the household measurement. It should be parseable as a standard datetime string (e.g., `YYYY-MM-DD HH:MM:SS`). It is interpreted as local household time.
- **`energy_consumption`**: The numeric electricity consumption during the measurement interval. 
  - **Unit:** `kWh` (Kilowatt-hours) consumed during the interval.
  - Negative values are considered invalid.

## Example CSV
```csv
timestamp,energy_consumption
2026-08-01 00:00,0.42
2026-08-01 00:15,0.38
2026-08-01 00:30,0.41
2026-08-01 00:45,0.36
2026-08-01 01:00,0.35
```

## Validation Rules
When a user uploads a CSV, it goes through a validation layer (`scripts/validate_user_csv.py`) that checks:
1. **Schema Check:** Ensures required columns are present.
2. **Timestamp Check:** Identifies unparseable values, missing values, duplicate timestamps, and gaps. Determines the likely sampling interval (e.g., 15 minutes, 1 hour).
3. **Values Check:** Ensures all energy consumption values are numeric, non-null, and non-negative.
4. **Original Data:** The validation layer never modifies the user's original uploaded data. Imputation and cleaning happen in later modules.

## Forecasting Readiness Levels
Based on the duration (history) of the data provided, the system assigns a forecasting readiness level:
- **Insufficient history (< 7 days):** Too short for reliable forecasting.
- **Basic (>= 7 days):** Can generate very short-term basic forecasts.
- **Good (>= 30 days):** Suitable for standard forecasting models.
- **Strong (>= 90 days):** Excellent for discovering seasonal trends and robust forecasting.

## Meaning of Statuses
- **`VALID`**: The file has a clean structure, valid data, and no apparent gaps or duplicates.
- **`VALID_WITH_WARNINGS`**: The file is structurally acceptable but contains issues (like gaps, duplicates, or insufficient history) that may affect the quality of forecasting.
- **`INVALID`**: The file cannot be processed due to critical errors (missing required columns, negative consumption values, or unreadable formatting).

## CLI Usage Example
To validate a CSV file from the command line, run:
```bash
python scripts/validate_user_csv.py path/to/user_file.csv
```
