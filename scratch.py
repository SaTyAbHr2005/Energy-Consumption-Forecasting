import pandas as pd
st_dt = pd.to_datetime("2026-07-15")
et_dt = pd.to_datetime("2026-09-05")
period_range = pd.period_range(start=st_dt, end=et_dt, freq='M')
print([str(p) for p in period_range])
print([str(p.year) for p in period_range])
p_start = pd.to_datetime("2026-08" + "-01")
p_end = p_start + pd.offsets.MonthEnd(0) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
print(p_start, p_end)
