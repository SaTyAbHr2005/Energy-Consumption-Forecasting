-- 1. Profiles Table
CREATE TABLE IF NOT EXISTS public.profiles (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    full_name TEXT,
    email TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Users can view their own profile" ON public.profiles FOR SELECT USING (auth.uid() = id);
CREATE POLICY "Users can update their own profile" ON public.profiles FOR UPDATE USING (auth.uid() = id);

-- Trigger for automatic profile creation
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO public.profiles (id, full_name, email)
    VALUES (new.id, new.raw_user_meta_data->>'full_name', new.email);
    RETURN new;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Drop trigger if exists to allow re-runs
DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
    AFTER INSERT ON auth.users
    FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();


-- 2. Uploaded Datasets Table
CREATE TABLE IF NOT EXISTS public.uploaded_datasets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
    file_name TEXT NOT NULL,
    storage_path TEXT NOT NULL,
    file_type TEXT,
    file_size BIGINT,
    record_count INTEGER,
    interval_minutes INTEGER,
    start_timestamp TIMESTAMPTZ,
    end_timestamp TIMESTAMPTZ,
    validation_status TEXT,
    analysis_status TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE public.uploaded_datasets ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Users can view their own datasets" ON public.uploaded_datasets FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY "Users can insert their own datasets" ON public.uploaded_datasets FOR INSERT WITH CHECK (auth.uid() = user_id);
CREATE POLICY "Users can update their own datasets" ON public.uploaded_datasets FOR UPDATE USING (auth.uid() = user_id);
CREATE POLICY "Users can delete their own datasets" ON public.uploaded_datasets FOR DELETE USING (auth.uid() = user_id);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_uploaded_datasets_user_id ON public.uploaded_datasets(user_id);
CREATE INDEX IF NOT EXISTS idx_uploaded_datasets_created_at ON public.uploaded_datasets(created_at);
CREATE INDEX IF NOT EXISTS idx_uploaded_datasets_user_time ON public.uploaded_datasets(user_id, created_at);


-- 3. Storage Bucket
INSERT INTO storage.buckets (id, name, public) 
VALUES ('energy-csv', 'energy-csv', false) 
ON CONFLICT (id) DO NOTHING;

-- Storage Policies
-- Note: 'storage.foldername(name)' returns an array of the path. Index 1 is the first folder (which should be the user_id)
CREATE POLICY "Users can upload their own CSVs" ON storage.objects FOR INSERT
WITH CHECK ( bucket_id = 'energy-csv' AND auth.uid()::text = (storage.foldername(name))[1] );

CREATE POLICY "Users can view their own CSVs" ON storage.objects FOR SELECT
USING ( bucket_id = 'energy-csv' AND auth.uid()::text = (storage.foldername(name))[1] );

CREATE POLICY "Users can delete their own CSVs" ON storage.objects FOR DELETE
USING ( bucket_id = 'energy-csv' AND auth.uid()::text = (storage.foldername(name))[1] );
