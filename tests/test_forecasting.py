import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

from src.forecasting import DataSplitter, NaiveForecaster, FeatureRebuilder

@pytest.fixture
def mock_time_series():
    dates = [datetime(2023, 1, 1) + timedelta(hours=i) for i in range(100)]
    df = pd.DataFrame({
        'timestamp': dates,
        'energy_kwh': np.random.rand(100) * 5,
        'lag_1': np.random.rand(100) * 5,
        'lag_24': np.random.rand(100) * 5
    })
    return df

def test_chronological_split(mock_time_series):
    train, val, test = DataSplitter.chronological_split(mock_time_series, train_ratio=0.7, val_ratio=0.15)
    
    # Check sizes
    assert len(train) == 70
    assert len(val) == 15
    assert len(test) == 15
    
    # Check chron order
    assert train['timestamp'].max() < val['timestamp'].min()
    assert val['timestamp'].max() < test['timestamp'].min()

def test_naive_forecaster(mock_time_series):
    naive = NaiveForecaster()
    
    res_1h = naive.predict_1h(mock_time_series.iloc[:10])
    assert 'predicted' in res_1h.columns
    assert 'actual' in res_1h.columns
    assert (res_1h['horizon'] == 1).all()
    assert (res_1h['model'] == 'Naive_1h').all()
    
    res_24h = naive.predict_24h(mock_time_series.iloc[:10])
    assert (res_24h['horizon'] == 24).all()
    assert (res_24h['model'] == 'Naive_24h').all()

def test_feature_rebuilder():
    dates = [datetime(2023, 1, 1) + timedelta(hours=i) for i in range(200)]
    df = pd.DataFrame({
        'timestamp': dates,
        'energy_kwh': np.ones(200) * 2.0
    })
    
    next_ts = pd.Timestamp("2023-01-09 08:00:00")
    feat_cols = ['year', 'month', 'day', 'hour', 'lag_1', 'lag_24', 'lag_168', 'rolling_mean_24']
    
    rebuilt = FeatureRebuilder.build_next_feature_vector(df, next_ts, p90_threshold=3.0, feature_cols=feat_cols)
    
    assert len(rebuilt) == 1
    assert rebuilt['year'].iloc[0] == 2023
    assert rebuilt['hour'].iloc[0] == 8
    
    # History is all 2.0
    assert rebuilt['lag_1'].iloc[0] == 2.0
    assert rebuilt['lag_24'].iloc[0] == 2.0
    assert rebuilt['lag_168'].iloc[0] == 2.0
    assert rebuilt['rolling_mean_24'].iloc[0] == 2.0
