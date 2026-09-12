import pytest
import pandas as pd
import numpy as np
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))
from src.model_evaluation import Evaluator

def test_metrics_calculation():
    evaluator = Evaluator(peak_threshold=2.0)
    actual = pd.Series([1.0, 2.0, 3.0, 4.0])
    predicted = pd.Series([1.0, 2.0, 3.0, 4.0])
    
    metrics = evaluator.calculate_metrics(actual, predicted)
    assert metrics['mae'] == 0.0
    assert metrics['rmse'] == 0.0
    assert metrics['mape'] == 0.0
    assert metrics['r2'] == 1.0
    
    # Introduce error
    predicted_err = pd.Series([2.0, 3.0, 4.0, 5.0])
    metrics_err = evaluator.calculate_metrics(actual, predicted_err)
    assert metrics_err['mae'] == 1.0
    assert metrics_err['rmse'] == 1.0
    # MAPE = (1/1 + 1/2 + 1/3 + 1/4)/4 * 100 = (1 + 0.5 + 0.333 + 0.25)/4 * 100 = 2.0833 / 4 * 100 = 52.0833
    assert np.isclose(metrics_err['mape'], 52.083333333333336)
    
def test_zero_handling_in_mape():
    evaluator = Evaluator(peak_threshold=2.0)
    actual = pd.Series([0.0, 1.0])
    predicted = pd.Series([1.0, 1.0])
    
    metrics = evaluator.calculate_metrics(actual, predicted)
    # The actual=0 should be ignored
    assert metrics['mape'] == 0.0 # because the 1.0 element has error 0.0

def test_peak_metrics():
    evaluator = Evaluator(peak_threshold=2.0)
    # >2.0 is a peak
    actual = pd.Series([1.0, 1.5, 2.5, 3.0, 0.5])
    predicted = pd.Series([1.0, 2.5, 2.5, 1.0, 0.5])
    # Peaks actual: [F, F, T, T, F]
    # Peaks pred:   [F, T, T, F, F]
    # TP = idx 2 (1)
    # FP = idx 1 (1)
    # FN = idx 3 (1)
    # Precision = 1 / (1 + 1) = 0.5
    # Recall = 1 / (1 + 1) = 0.5
    # F1 = 0.5
    
    metrics = evaluator.calculate_peak_metrics(actual, predicted)
    assert metrics['precision'] == 0.5
    assert metrics['recall'] == 0.5
    assert metrics['f1_score'] == 0.5

def test_baseline_improvement():
    assert Evaluator.calculate_improvement(10.0, 8.0, lower_is_better=True) == 20.0
    assert Evaluator.calculate_improvement(10.0, 12.0, lower_is_better=True) == -20.0
    assert Evaluator.calculate_improvement(0.0, 5.0, lower_is_better=True) == 0.0
