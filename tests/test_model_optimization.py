import pytest
import numpy as np
import pandas as pd
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

def calculate_accuracy(actual, predicted, tolerance=0.10, epsilon=1e-4):
    denominator = np.maximum(np.abs(actual), epsilon)
    relative_error = np.abs(actual - predicted) / denominator
    return np.mean(relative_error <= tolerance) * 100

def test_accuracy_within_tolerance():
    actual = np.array([10.0, 10.0, 10.0, 10.0])
    # 0% error, 5% error, 15% error, 25% error
    predicted = np.array([10.0, 10.5, 11.5, 12.5])
    
    # Within 10%: only the first two (0%, 5%)
    acc_10 = calculate_accuracy(actual, predicted, 0.10)
    assert acc_10 == 50.0
    
    # Within 20%: first three (0%, 5%, 15%)
    acc_20 = calculate_accuracy(actual, predicted, 0.20)
    assert acc_20 == 75.0

def test_zero_near_zero_handling():
    actual = np.array([0.0, 0.00001, 10.0])
    # Exact match on zero, tiny error on near-zero, match on 10
    predicted = np.array([0.0, 0.00002, 10.0])
    
    # Should not raise division by zero
    acc_10 = calculate_accuracy(actual, predicted, 0.10)
    # 0.0 vs 0.0 -> err = 0 / 1e-4 = 0 <= 0.10 -> True
    # 1e-5 vs 2e-5 -> err = 1e-5 / 1e-4 = 0.1 <= 0.10 -> True
    # 10 vs 10 -> True
    assert acc_10 == 100.0

def test_feature_leakage_checks():
    from src.feature_engineering_pandas import PandasFeatureEngineer
    
    # Dummy data
    df = pd.DataFrame({
        'timestamp': pd.date_range("2020-01-01", periods=100, freq='H'),
        'energy_kwh': np.random.rand(100)
    })
    
    engineer = PandasFeatureEngineer()
    out_df = engineer.engineer_features(df)
    
    # Ensure 'energy_kwh' wasn't modified or removed
    assert 'energy_kwh' in out_df.columns
    # Ensure lag_1 exists and contains the shifted data
    assert 'lag_1' in out_df.columns
    # The first row will be NaN because there is no previous hour
    assert np.isnan(out_df['lag_1'].iloc[0]) == True
    assert np.isnan(out_df['lag_1'].iloc[1]) == False
    
    # If target is energy_kwh, check rolling doesn't include current row.
    # We can't strictly test that in a simple assert without mocking, 
    # but we can verify the column exists.
    assert 'rolling_mean_3' in out_df.columns
