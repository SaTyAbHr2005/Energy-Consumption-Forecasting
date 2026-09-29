# Module 10: R (plumber) Backend and Next.js Frontend

Module 10 exposes the completed forecasting and Module 9 decision-support
artifacts through an R (plumber) API and a responsive multi-page Next.js application.

## Run the backend

From the project root (needs R 4.1+ and the packages listed in the README):

```bash
Rscript backend/run.R
```

The API is available at `http://localhost:8000`. Backend layout:

* `backend/run.R` - entry point (loads `.env`, starts plumber)
* `backend/R/routes.R` - HTTP routes, CORS, auth, error handling
* `backend/R/analysis.R` - data loading, feature engineering, XGBoost forecast, dashboard
* `backend/R/smart_grid.R` - peak detection, time-of-use cost, load shifting, recommendations
* `backend/R/validator.R` - CSV upload validation and storage
* `backend/R/supabase.R` - Supabase Auth / PostgREST / Storage client
* `backend/R/artifacts.R` - endpoints serving the pre-computed files in `results/`

The XGBoost models in `models/final/` were trained offline with Python and are
loaded unchanged by the R `xgboost` package. `backend/tests/run_checks.R`
verifies that the R feature builder and prediction match the Python reference.

## Run the frontend

From `frontend/`:

```bash
npm install
npm run dev
```

The dashboard is available at `http://localhost:3000`. Set
`NEXT_PUBLIC_API_URL` when the backend runs on another URL.

The application routes are `/`, `/upload`, `/dashboard`, `/forecast`,
`/analytics`, `/smart-grid`, and `/recommendations`. A successful upload stores
only its temporary `upload_id` in browser local storage so these routes can
continue using the same household analysis; CSV contents are not stored in the
browser. Without an active upload, the dashboard shows an empty state while
the stored UCI/demo artifacts remain explicitly labelled on pages that expose
them.

## API surfaces

* `GET /health`
* `POST /api/upload` validates `timestamp,energy_consumption` CSV files using
  the existing Module 2 validator and returns a temporary `upload_id`.
* `POST /api/forecast/user?upload_id=...&horizon=1|24` converts interval kWh
  to hourly sums, builds the exact final-model feature schema, loads the
  existing XGBoost artifact (`xgboost_1h.json` for the next hour,
  `xgboost_24h_direct.json` for the next 24 hours), and returns user-specific
  forecast and smart-grid analysis. It never retrains or writes model artifacts.
  The 24-hour model was trained as "features of hour t -> kWh of hour t + 23",
  so hour k of the forecast uses the feature row of hour last + k - 23 (the last
  23 history rows plus the next hour): one call, no recursive error build-up.
* `GET /api/bills` returns the user's bills ordered by bill month, newest first
  (not by upload time), which the month-over-month comparison relies on.
* `GET /api/forecast?horizon=1|24` serves the stored XGBoost forecast output.
* `GET /api/analytics/summary`, `/hourly`, `/daily`, and `/weekday`
* `GET /api/smart-grid/summary`, `/peaks`, `/tou`, `/load-shifting`, and
  `/sensitivity`
* `GET /api/recommendations`

The completed workflow is:

```text
User CSV -> validation -> hourly preparation -> feature engineering
-> existing XGBoost inference -> forecast -> smart-grid insights -> recommendations
```

The final feature builder requires at least 169 hourly observations (the
168-hour lag plus the prediction row) for the 1-hour forecast and 192 for the
24-hour forecast (23 more, because its earliest feature row is 23 hours back).
Insufficient uploads return a structured
`insufficient_history` response and never fall back to UCI results. Uploaded
energy values are interval kWh and are summed when resampling; they are not
divided by 60. User thresholds are calculated from the uploaded hourly history
and labelled `User Dataset Threshold`. Stored UCI-derived artifacts remain
separate and clearly labelled as historical, forecast, or simulated values.
TOU costs are illustrative and savings are potential, not guaranteed.
