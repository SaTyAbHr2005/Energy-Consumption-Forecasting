import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
import json

class Evaluator:
    def __init__(self, peak_threshold: float):
        self.peak_threshold = peak_threshold

    def calculate_metrics(self, actual: pd.Series, predicted: pd.Series) -> dict:
        """Calculates regression and forecasting metrics."""
        mae = mean_absolute_error(actual, predicted)
        rmse = np.sqrt(mean_squared_error(actual, predicted))
        r2 = r2_score(actual, predicted)
        
        # Safe MAPE calculation
        # Filter out exact zero or extremely close to zero actuals to avoid inf
        epsilon = 1e-8
        mask = actual > epsilon
        if mask.sum() > 0:
            mape = np.mean(np.abs((actual[mask] - predicted[mask]) / actual[mask])) * 100
        else:
            mape = np.nan
            
        return {
            "mae": float(mae),
            "rmse": float(rmse),
            "mape": float(mape),
            "r2": float(r2),
            "prediction_count": int(len(actual))
        }
        
    def calculate_peak_metrics(self, actual: pd.Series, predicted: pd.Series) -> dict:
        """Calculates classification metrics for peak demand (values > threshold)."""
        actual_peaks = actual > self.peak_threshold
        predicted_peaks = predicted > self.peak_threshold
        
        tp = (actual_peaks & predicted_peaks).sum()
        fp = (~actual_peaks & predicted_peaks).sum()
        fn = (actual_peaks & ~predicted_peaks).sum()
        
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1_score = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
        
        return {
            "precision": float(precision),
            "recall": float(recall),
            "f1_score": float(f1_score),
            "true_positives": int(tp),
            "false_positives": int(fp),
            "false_negatives": int(fn)
        }

    @staticmethod
    def calculate_improvement(baseline_metric: float, model_metric: float, lower_is_better: bool = True) -> float:
        """Calculates percentage improvement of model over baseline."""
        if pd.isna(baseline_metric) or baseline_metric == 0:
            return 0.0
        if lower_is_better:
            return ((baseline_metric - model_metric) / baseline_metric) * 100
        else:
            return ((model_metric - baseline_metric) / baseline_metric) * 100
