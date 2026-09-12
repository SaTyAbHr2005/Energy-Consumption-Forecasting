
def get_user_periods(user_id: str) -> dict[str, Any]:
    from backend.services.auth_service import supabase_admin
    res = supabase_admin.table("uploaded_datasets").select("id, start_timestamp, end_timestamp").eq("user_id", user_id).execute()
    if not res.data:
        return {"periods": [], "years": [], "latest_period": None, "latest_upload_id": None}
    
    months = set()
    years = set()
    latest_ts = None
    latest_month = None
    latest_upload_id = None
    
    for row in res.data:
        st = row.get("start_timestamp")
        et = row.get("end_timestamp")
        if not st or not et: continue
        try:
            st_dt = pd.to_datetime(st)
            et_dt = pd.to_datetime(et)
            period_range = pd.period_range(start=st_dt, end=et_dt, freq='M')
            for p in period_range:
                months.add(str(p))
                years.add(str(p.year))
            
            if latest_ts is None or et_dt > latest_ts:
                latest_ts = et_dt
                latest_month = str(et_dt.to_period('M'))
                latest_upload_id = row["id"]
        except Exception:
            continue
            
    months = sorted(list(months), reverse=True)
    years = sorted(list(years), reverse=True)
    return {
        "periods": months,
        "years": years,
        "latest_period": latest_month,
        "latest_upload_id": latest_upload_id
    }

def load_user_data_for_period(user_id: str, period: str) -> pd.DataFrame:
    from backend.services.auth_service import supabase_admin
    is_year = len(period) == 4
    res = supabase_admin.table("uploaded_datasets").select("id, start_timestamp, end_timestamp").eq("user_id", user_id).execute()
    if not res.data:
        return pd.DataFrame()
        
    dfs = []
    for row in res.data:
        st = row.get("start_timestamp")
        et = row.get("end_timestamp")
        if not st or not et: continue
        
        try:
            st_dt = pd.to_datetime(st)
            et_dt = pd.to_datetime(et)
            if is_year:
                p_start = pd.to_datetime(f"{period}-01-01")
                p_end = pd.to_datetime(f"{period}-12-31 23:59:59")
            else:
                p_start = pd.to_datetime(f"{period}-01")
                p_end = p_start + pd.offsets.MonthEnd(0) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
                
            if st_dt <= p_end and et_dt >= p_start:
                df = _load_hourly(row["id"])
                df = df[(df["timestamp"] >= p_start) & (df["timestamp"] <= p_end)]
                if not df.empty:
                    dfs.append(df)
        except Exception:
            pass
            
    if not dfs:
        return pd.DataFrame()
        
    combined = pd.concat(dfs, ignore_index=True)
    combined = combined.groupby("timestamp", as_index=False)["energy_kwh"].mean()
    combined = combined.sort_values("timestamp")
    return combined
