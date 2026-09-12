# Deployment Guide: EnergySense

This document outlines the deployment strategy for the EnergySense project using a 100% free-tier architecture.

## 1. Architecture

*   **Frontend**: Hosted on [Vercel](https://vercel.com) (Hobby Tier). Next.js provides static and SSR capabilities.
*   **Backend**: Hosted on [Render](https://render.com) (Web Service Free Tier). FastAPI runs the API and XGBoost model inferences.
*   **Database & Auth**: Hosted on [Supabase](https://supabase.com) (Free Tier). Provides PostgreSQL for data storage, Authentication, and Storage buckets for CSV files.
*   *Note: PySpark is strictly for the research/data-processing pipeline and is not deployed to the production web server to comply with the free-tier memory limits.*

## 2. GitHub Setup

Ensure your local project has no sensitive secrets committed.
```bash
# Verify working tree is clean and secrets are ignored
git status
```
The `.gitignore` has been thoroughly configured to exclude `.env`, virtual environments, local SQLite DBs, and raw datasets. Push this repository to your GitHub account.

## 3. Supabase Setup

Your Supabase project is already configured and integrated into the app.
*   **PostgreSQL**: Contains `uploaded_datasets` and `user_bills` tables.
*   **Auth**: Row Level Security (RLS) policies are active.
*   **Storage**: Contains the `energy-csv` bucket.

### Environment Variables for Supabase
You will need the following from your Supabase Dashboard (Project Settings -> API):
*   `NEXT_PUBLIC_SUPABASE_URL`
*   `NEXT_PUBLIC_SUPABASE_ANON_KEY`
*   `SUPABASE_URL` (For Backend)
*   `SUPABASE_SERVICE_ROLE_KEY` (For Backend - **SECRET**)

## 4. Render Setup (FastAPI Backend)

Render is used instead of Vercel for the backend because XGBoost and Pandas combined exceed Vercel's 250MB serverless function limit.

1.  Log in to [Render](https://render.com).
2.  Click **New +** and select **Web Service**.
3.  Connect your GitHub repository.
4.  Configure the service:
    *   **Name**: `energysense-backend`
    *   **Root Directory**: `.` (leave blank or explicitly type `.`)
    *   **Environment**: `Python 3`
    *   **Build Command**: `pip install -r backend/requirements.txt`
    *   **Start Command**: `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`
    *   **Instance Type**: `Free`
5.  Add the following Environment Variables in Render:
    *   `SUPABASE_URL`: `<your-supabase-url>`
    *   `SUPABASE_SERVICE_ROLE_KEY`: `<your-supabase-service-role-key>`
    *   `FRONTEND_URL`: `https://<your-vercel-domain>` (You can add this after deploying Vercel).
6.  Click **Create Web Service**.

*Note: Render's Free tier will put the service to sleep after 15 minutes of inactivity. The first request after sleeping will take ~30-50 seconds (Cold Start). Subsequent requests are fast.*

## 5. Vercel Setup (Next.js Frontend)

1.  Log in to [Vercel](https://vercel.com).
2.  Click **Add New -> Project**.
3.  Import the same GitHub repository.
4.  Configure the deployment:
    *   **Project Name**: `energysense-frontend`
    *   **Framework Preset**: `Next.js`
    *   **Root Directory**: `frontend`
    *   **Build Command**: `npm run build`
5.  Add the following Environment Variables in Vercel:
    *   `NEXT_PUBLIC_SUPABASE_URL`: `<your-supabase-url>`
    *   `NEXT_PUBLIC_SUPABASE_ANON_KEY`: `<your-supabase-anon-key>`
    *   `NEXT_PUBLIC_API_URL`: `https://<your-render-url>` (Get this from your Render dashboard after step 4).
6.  Click **Deploy**.

## 6. Testing the Deployment

Once both are deployed, test the E2E flow:
1.  Visit your Vercel URL.
2.  Log in with your existing test user.
3.  Upload a new CSV dataset.
4.  Verify that the dashboard loads the forecast, which proves the Render backend successfully started, loaded the ML artifacts, and communicated with Supabase Storage.
5.  Check the `My Data` page and verify that deleting a dataset works (proves CORS and DELETE endpoints are functional).

## 7. Security Considerations

*   **CORS**: The backend is configured to only accept requests from `localhost` and your specified `FRONTEND_URL`.
*   **Secrets**: The `SUPABASE_SERVICE_ROLE_KEY` bypasses all Row Level Security. It is strictly injected into the Render backend environment variables and NEVER exposed to the frontend or committed to Git.
*   **File System**: The backend uses the ephemeral `/tmp` directory (`tempfile.gettempdir()`) for CSV processing, making it fully compatible with read-only serverless/container environments.
