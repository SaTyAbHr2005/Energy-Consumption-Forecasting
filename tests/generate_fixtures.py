import pandas as pd
import numpy as np
from pathlib import Path

def generate_fixtures():
    fixtures_dir = Path(__file__).resolve().parent / 'fixtures'
    fixtures_dir.mkdir(exist_ok=True)
    
    # 1. Valid energy (31 days, 15 min interval)
    dates = pd.date_range(start='2026-08-01 00:00:00', periods=3000, freq='15min')
    df_valid = pd.DataFrame({
        'timestamp': dates,
        'energy_consumption': np.random.uniform(0.1, 2.5, size=len(dates))
    })
    df_valid.to_csv(fixtures_dir / 'sample_valid_energy.csv', index=False)
    
    # 2. Invalid schema (missing energy_consumption)
    df_invalid_schema = pd.DataFrame({
        'timestamp': pd.date_range(start='2026-08-01', periods=5, freq='15min'),
        'temperature': [22, 23, 21, 22, 24]
    })
    df_invalid_schema.to_csv(fixtures_dir / 'sample_invalid_schema.csv', index=False)
    
    # 3. Invalid values (negative and non-numeric)
    df_invalid_values = pd.DataFrame({
        'timestamp': pd.date_range(start='2026-08-01', periods=5, freq='15min'),
        'energy_consumption': [0.42, -0.1, 'abc', None, 0.5]
    })
    df_invalid_values.to_csv(fixtures_dir / 'sample_invalid_values.csv', index=False)
    
    # 4. Short history (1 day)
    dates_short = pd.date_range(start='2026-08-01 00:00:00', periods=96, freq='15min')
    df_short = pd.DataFrame({
        'timestamp': dates_short,
        'energy_consumption': np.random.uniform(0.1, 2.5, size=len(dates_short))
    })
    df_short.to_csv(fixtures_dir / 'sample_short_history.csv', index=False)

    # 5. Gaps and duplicates
    dates_gaps = pd.date_range(start='2026-08-01 00:00:00', periods=10, freq='15min').tolist()
    dates_gaps.remove(dates_gaps[3]) # create gap
    dates_gaps.append(dates_gaps[5]) # duplicate
    df_gaps = pd.DataFrame({
        'timestamp': dates_gaps,
        'energy_consumption': np.random.uniform(0.1, 2.5, size=len(dates_gaps))
    })
    df_gaps.to_csv(fixtures_dir / 'sample_gaps_duplicates.csv', index=False)

    print("Fixtures generated.")

if __name__ == '__main__':
    generate_fixtures()
