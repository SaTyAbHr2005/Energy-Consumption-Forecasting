# Module 10: FastAPI Backend and Next.js Frontend

Module 10 exposes the completed forecasting and Module 9 decision-support
artifacts through a FastAPI API and a responsive multi-page Next.js application.

## Run the backend

From the project root:

```bash
pip install -r requirements.txt
uvicorn backend.main:app --reload
```

The API is available at `http://localhost:8000`. Interactive API
documentation is available at `/docs`.

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
  existing XGBoost artifact, and returns user-specific forecast and
  smart-grid analysis. It never retrains or writes model artifacts.
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
168-hour lag plus the prediction row). Insufficient uploads return a structured
`insufficient_history` response and never fall back to UCI results. Uploaded
energy values are interval kWh and are summed when resampling; they are not
divided by 60. User thresholds are calculated from the uploaded hourly history
and labelled `User Dataset Threshold`. Stored UCI-derived artifacts remain
separate and clearly labelled as historical, forecast, or simulated values.
TOU costs are illustrative and savings are potential, not guaranteed.
