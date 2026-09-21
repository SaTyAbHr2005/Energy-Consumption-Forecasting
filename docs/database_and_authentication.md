# Database and Authentication Architecture

This document describes the Supabase-backed authentication, database, and storage layer implemented in the EnergySense project.

## Overview

The EnergySense architecture uses Supabase to provide secure user authentication, persistent metadata storage, and reliable binary file storage. This ensures that users can securely log in, upload their smart-meter CSV data, and revisit those datasets in the future without needing to re-upload them.

- **Frontend**: Next.js App Router (React)
- **Backend**: R (plumber)
- **Database/Auth**: Supabase (PostgreSQL + GoTrue + Storage)

## Authentication Flow

1. **User Sign Up / Log In**: The user authenticates through the Next.js frontend (`/login` or `/register`) using `@supabase/ssr`.
2. **Session Storage**: Supabase securely stores the session tokens in browser cookies via Next.js Middleware (`frontend/utils/supabase/middleware.ts`).
3. **Route Protection (Frontend)**: The Next.js middleware inspects incoming requests. If a user attempts to access a protected route (e.g., `/dashboard`, `/upload`) without a valid session cookie, they are redirected to `/login`.
4. **Backend API Authorization**: 
   - When the frontend calls a protected R (plumber) backend endpoint (e.g., `/api/upload`, `/api/forecast/user`), it includes the JWT token in the `Authorization` header (`Bearer <token>`).
   - The R backend validates the JWT by calling Supabase Auth (`GET /auth/v1/user`) with the Service Role key (`sb_get_user_id()` in `backend/R/supabase.R`). If invalid, it returns a `401 Unauthorized`.

## Persistent Storage Flow (CSV Uploads)

1. **Upload Request**: The frontend POSTs the CSV file to the `/api/upload` endpoint, along with the Bearer token.
2. **Validation**: The backend runs the standard module validations to check timestamp integrity, energy values, and interval lengths.
3. **Persistence**:
   - The backend uploads the raw CSV bytes to Supabase Storage in the `energy-csv` bucket.
   - The file is stored at `<user_id>/<upload_id>/<filename>`.
   - The backend inserts a metadata record into the `uploaded_datasets` PostgreSQL table, capturing metrics like the number of records and analysis status.
4. **Row Level Security (RLS)**: The `uploaded_datasets` table and the `energy-csv` storage bucket enforce RLS. Users can *only* insert, select, update, or delete data where `user_id = auth.uid()`.

## Future Proofing

This architecture separates the core analytics engine from the data persistence layer. Because metadata is tracked in `uploaded_datasets`, future features such as **Electricity Bill OCR** can easily be integrated by introducing new tables (e.g., `utility_bills`) that link via foreign keys back to the `profiles` table. The forecasting engine remains untouched.

## Electricity bill OCR

`POST /api/upload/bill` runs real OCR (`backend/R/ocr.R`: the `tesseract` and `magick` R packages with English + Marathi language data) on the uploaded image and reads the **bill month**, the **amount payable** and the **units consumed** from an MSEDCL (Mahavitaran) bill. The image is converted to grayscale, upscaled and OCR'd in sparse-text mode; the parser has fallbacks for garbled labels. If any field cannot be read, the API answers `422` and stores nothing, so no made-up numbers are ever saved. One bill per month per user (`409` for a duplicate). PDFs are not supported; upload a JPG or PNG. The Docker image installs the OCR libraries (see `Dockerfile`).
