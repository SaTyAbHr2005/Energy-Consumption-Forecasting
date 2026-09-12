# Database and Authentication Architecture

This document describes the Supabase-backed authentication, database, and storage layer implemented in the EnergySense project.

## Overview

The EnergySense architecture uses Supabase to provide secure user authentication, persistent metadata storage, and reliable binary file storage. This ensures that users can securely log in, upload their smart-meter CSV data, and revisit those datasets in the future without needing to re-upload them.

- **Frontend**: Next.js App Router (React)
- **Backend**: FastAPI (Python)
- **Database/Auth**: Supabase (PostgreSQL + GoTrue + Storage)

## Authentication Flow

1. **User Sign Up / Log In**: The user authenticates through the Next.js frontend (`/login` or `/register`) using `@supabase/ssr`.
2. **Session Storage**: Supabase securely stores the session tokens in browser cookies via Next.js Middleware (`frontend/utils/supabase/middleware.ts`).
3. **Route Protection (Frontend)**: The Next.js middleware inspects incoming requests. If a user attempts to access a protected route (e.g., `/dashboard`, `/upload`) without a valid session cookie, they are redirected to `/login`.
4. **Backend API Authorization**: 
   - When the frontend calls a protected FastAPI backend endpoint (e.g., `/api/upload`, `/api/forecast/user`), it includes the JWT token in the `Authorization` header (`Bearer <token>`).
   - The FastAPI backend validates the JWT using the Supabase Service Role key (`supabase_admin.auth.get_user(token)`) in `backend/services/auth_service.py`. If invalid, it returns a `401 Unauthorized`.

## Persistent Storage Flow (CSV Uploads)

1. **Upload Request**: The frontend POSTs the CSV file to the FastAPI `/api/upload` endpoint, along with the Bearer token.
2. **Validation**: The backend runs the standard module validations to check timestamp integrity, energy values, and interval lengths.
3. **Persistence**:
   - The backend uploads the raw CSV bytes to Supabase Storage in the `energy-csv` bucket.
   - The file is stored at `<user_id>/<upload_id>/<filename>`.
   - The backend inserts a metadata record into the `uploaded_datasets` PostgreSQL table, capturing metrics like the number of records and analysis status.
4. **Row Level Security (RLS)**: The `uploaded_datasets` table and the `energy-csv` storage bucket enforce RLS. Users can *only* insert, select, update, or delete data where `user_id = auth.uid()`.

## Future Proofing

This architecture separates the core analytics engine from the data persistence layer. Because metadata is tracked in `uploaded_datasets`, future features such as **Electricity Bill OCR** can easily be integrated by introducing new tables (e.g., `utility_bills`) that link via foreign keys back to the `profiles` table. The forecasting engine remains untouched.
