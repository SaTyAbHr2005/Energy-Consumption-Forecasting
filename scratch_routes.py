
@app.get("/api/user/periods")
def get_periods(user = Depends(get_current_user)) -> dict[str, Any]:
    return get_user_periods(user.id)

@app.get("/api/user/dashboard")
def get_dashboard(period: str | None = None, user = Depends(get_current_user)) -> dict[str, Any]:
    # Default to latest period if none provided
    if not period:
        periods = get_user_periods(user.id)
        period = periods.get("latest_period")
        if not period:
            raise HTTPException(status_code=404, detail="No data available")
            
    # Load and combine data
    df = load_user_data_for_period(user.id, period)
    if df.empty:
        raise HTTPException(status_code=404, detail=f"No data is available for {period}.")
        
    is_year = len(period) == 4
    
    if is_year:
        # Aggregate by month
        df['month'] = df['timestamp'].dt.strftime('%b')
        df['month_num'] = df['timestamp'].dt.month
        monthly = df.groupby(['month', 'month_num'])['energy_kwh'].sum().reset_index()
        monthly = monthly.sort_values('month_num')
        return {
            "period": period,
            "is_year": True,
            "monthly_data": monthly[['month', 'energy_kwh']].to_dict(orient="records"),
            "total_consumption": float(df['energy_kwh'].sum()),
            "peak_consumption": float(df.groupby('month_num')['energy_kwh'].sum().max()) if not monthly.empty else 0,
            "months_with_data": len(monthly)
        }
    else:
        # Aggregate by day and hour
        df['date'] = df['timestamp'].dt.strftime('%Y-%m-%d')
        daily = df.groupby('date')['energy_kwh'].sum().reset_index()
        
        df['hour'] = df['timestamp'].dt.strftime('%H:00')
        hourly = df.groupby('hour')['energy_kwh'].mean().reset_index()
        
        return {
            "period": period,
            "is_year": False,
            "total_consumption": float(df['energy_kwh'].sum()),
            "daily_average": float(daily['energy_kwh'].mean()) if not daily.empty else 0,
            "peak_consumption": float(df['energy_kwh'].max()),
            "lowest_consumption": float(df['energy_kwh'].min()),
            "daily_data": daily.to_dict(orient="records"),
            "hourly_profile": hourly.to_dict(orient="records")
        }
