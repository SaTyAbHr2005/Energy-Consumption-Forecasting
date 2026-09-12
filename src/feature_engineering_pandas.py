import pandas as pd
import numpy as np

class PandasFeatureEngineer:
    def __init__(self):
        pass
        
    def engineer_features(self, df: pd.DataFrame, target_col: str = "energy_kwh", p90_threshold: float = 2.28) -> pd.DataFrame:
        df = df.copy()
        df = df.sort_values('timestamp').reset_index(drop=True)
        
        # Calendar & Cyclical
        df['year'] = df['timestamp'].dt.year
        df['month'] = df['timestamp'].dt.month
        df['day'] = df['timestamp'].dt.day
        df['day_of_week'] = df['timestamp'].dt.dayofweek
        df['hour'] = df['timestamp'].dt.hour
        df['is_weekend'] = df['day_of_week'].isin([5, 6]).astype(int)
        
        df['hour_sin'] = np.sin(2 * np.pi * df['hour'] / 24)
        df['hour_cos'] = np.cos(2 * np.pi * df['hour'] / 24)
        df['dow_sin'] = np.sin(2 * np.pi * df['day_of_week'] / 7)
        df['dow_cos'] = np.cos(2 * np.pi * df['day_of_week'] / 7)
        df['month_sin'] = np.sin(2 * np.pi * df['month'] / 12)
        df['month_cos'] = np.cos(2 * np.pi * df['month'] / 12)
        
        # Seasonal Interaction Features
        df['hour_x_dow'] = df['hour'] * df['day_of_week']
        df['hour_x_weekend'] = df['hour'] * df['is_weekend']
        df['month_x_hour'] = df['month'] * df['hour']
        
        # Lags
        lags = [1, 2, 3, 4, 6, 8, 12, 18, 24, 36, 48, 72, 96, 120, 144, 168]
        for lag in lags:
            df[f'lag_{lag}'] = df[target_col].shift(lag)
            
        # Rolling Features (Strictly historical: shift(1) means we start rolling from the previous hour)
        rolling_means = [2, 3, 6, 12, 24, 48, 72, 168]
        for w in rolling_means:
            df[f'rolling_mean_{w}'] = df[target_col].shift(1).rolling(window=w, min_periods=w).mean()
            
        rolling_stds = [6, 12, 24, 48, 168]
        for w in rolling_stds:
            df[f'rolling_std_{w}'] = df[target_col].shift(1).rolling(window=w, min_periods=w).std()
            
        rolling_minmax = [24, 168]
        for w in rolling_minmax:
            df[f'rolling_min_{w}'] = df[target_col].shift(1).rolling(window=w, min_periods=w).min()
            df[f'rolling_max_{w}'] = df[target_col].shift(1).rolling(window=w, min_periods=w).max()
            df[f'rolling_median_{w}'] = df[target_col].shift(1).rolling(window=w, min_periods=w).median()
            
        # Exponentially Weighted Features (strictly historical)
        ewm_spans = [3, 6, 12, 24, 48]
        for span in ewm_spans:
            df[f'ewm_{span}'] = df[target_col].shift(1).ewm(span=span, adjust=False).mean()
            
        # Trend Features
        trend_horizons = [1, 3, 6, 12, 24, 48]
        for h in trend_horizons:
            # Trend is how much it changed from (current - h) to current (which is lag_1)
            # So trend_1h = lag_1 - lag_2
            # trend_3h = lag_1 - lag_4
            if f'lag_{h+1}' in df.columns:
                df[f'trend_{h}h'] = df['lag_1'] - df[f'lag_{h+1}']
            else:
                df[f'trend_{h}h'] = df['lag_1'] - df[target_col].shift(h+1)
                
        # Contextual
        df['is_high_demand_previous_hour'] = (df['lag_1'] >= p90_threshold).astype(int)
        
        # Max lag is 168 (7 days)
        df_clean = df.copy()
        
        return df_clean
