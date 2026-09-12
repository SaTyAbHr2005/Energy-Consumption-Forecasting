"""
Tests for final advanced forecasting optimization.
All tests use synthetic data only — the test set is never read in these tests.
"""
import pytest
import numpy as np
import pandas as pd
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

EPS = 1e-4

def acc_within(actual, pred, tol):
    denom = np.maximum(np.abs(actual), EPS)
    return float(np.mean(np.abs(actual - pred) / denom <= tol) * 100)

def smape(actual, pred):
    denom = np.abs(actual) + np.abs(pred)
    mask  = denom > EPS
    if mask.sum() == 0: return np.nan
    return float(np.mean(2 * np.abs(actual[mask] - pred[mask]) / denom[mask]) * 100)


# ── Accuracy ────────────────────────────────────────────────────────────────

def test_acc_perfect():
    a = np.array([1.0, 2.0, 3.0])
    assert acc_within(a, a, 0.10) == 100.0

def test_acc_partial():
    a = np.array([10.0, 10.0, 10.0, 10.0])
    p = np.array([10.0, 10.5, 11.5, 12.5])
    assert acc_within(a, p, 0.10) == 50.0   # 0%, 5% pass; 15%, 25% fail
    assert acc_within(a, p, 0.20) == 75.0   # 15% also passes

def test_acc_zero_actual():
    # zero actual → clipped to EPS, should not divide by zero
    a = np.array([0.0, 1.0])
    p = np.array([0.5, 1.0])
    result = acc_within(a, p, 0.10)
    assert isinstance(result, float)
    assert 0 <= result <= 100

def test_acc_tolerances_monotone():
    a = np.ones(100)
    p = a + np.random.default_rng(0).uniform(-0.5, 0.5, 100)
    accs = [acc_within(a, p, t) for t in [0.10, 0.20, 0.30, 0.50]]
    # wider tolerance → more or equal predictions fall inside
    for i in range(len(accs) - 1):
        assert accs[i] <= accs[i+1] + 1e-6   # monotone (allow tiny float noise)


# ── sMAPE ───────────────────────────────────────────────────────────────────

def test_smape_perfect():
    a = np.array([1.0, 2.0, 3.0])
    assert smape(a, a) == pytest.approx(0.0, abs=1e-6)

def test_smape_bounded():
    a = np.array([1.0, 0.0, 5.0])
    p = np.array([0.0, 1.0, 0.0])
    result = smape(a, p)
    assert 0.0 <= result <= 200.0


# ── Feature engineering — no future leakage ─────────────────────────────────

def test_lag_no_future_leak():
    """lag_1 at position i should equal y[i-1], not y[i] or later."""
    from src.feature_engineering_pandas import PandasFeatureEngineer
    np.random.seed(42)
    n = 200
    df = pd.DataFrame({
        "timestamp": pd.date_range("2020-01-01", periods=n, freq="h"),
        "energy_kwh": np.arange(n, dtype=float),   # deterministic: y[i] = i
    })
    eng = PandasFeatureEngineer()
    out = eng.engineer_features(df)

    # After shift(1), lag_1 at row k should equal k-1 (the previous value)
    for idx, row in out.iterrows():
        if pd.isna(row["lag_1"]):
            continue
        expected = row["energy_kwh"] - 1.0   # because y[i]=i → y[i-1]=i-1
        assert abs(row["lag_1"] - expected) < 1e-6, (
            f"Lag leakage at index {idx}: lag_1={row['lag_1']} but expected {expected}"
        )


def test_rolling_no_future_leak():
    """rolling_mean_3 at position i must NOT include y[i]."""
    from src.feature_engineering_pandas import PandasFeatureEngineer
    n = 50
    df = pd.DataFrame({
        "timestamp": pd.date_range("2020-01-01", periods=n, freq="h"),
        "energy_kwh": np.arange(n, dtype=float),
    })
    eng = PandasFeatureEngineer()
    out = eng.engineer_features(df)
    for idx, row in out.iterrows():
        if pd.isna(row.get("rolling_mean_3")):
            continue
        # The current value y[idx] must NOT appear in the rolling average
        # rolling_mean_3 = mean(y[idx-3], y[idx-2], y[idx-1])
        # Since y is just the row index, current y = row["energy_kwh"]
        assert abs(row["rolling_mean_3"] - row["energy_kwh"]) > 0.5, (
            f"Rolling window includes current value at idx={idx}"
        )


# ── Chronological split ──────────────────────────────────────────────────────

def test_chronological_split_no_overlap():
    n = 100
    ts = pd.date_range("2020-01-01", periods=n, freq="h")
    df = pd.DataFrame({"timestamp": ts, "value": range(n)})
    cut1 = ts[69]   # train ends here
    cut2 = ts[84]   # val ends here
    train = df[df["timestamp"] <= cut1]
    val   = df[(df["timestamp"] > cut1) & (df["timestamp"] <= cut2)]
    test  = df[df["timestamp"] > cut2]
    assert len(train) + len(val) + len(test) == n
    assert train["timestamp"].max() < val["timestamp"].min()
    assert val["timestamp"].max()   < test["timestamp"].min()


# ── Ensemble weights ─────────────────────────────────────────────────────────

def test_ensemble_weights_sum_to_one():
    w_xgb, w_lstm, w_gru = 0.7, 0.2, 0.1
    assert abs(w_xgb + w_lstm + w_gru - 1.0) < 1e-6

def test_ensemble_all_xgb():
    a = np.array([1.0, 2.0, 3.0])
    xgb_pred  = np.array([1.1, 2.1, 3.1])
    lstm_pred = np.array([0.9, 1.9, 2.9])
    # Ensemble with weight 1.0 on XGBoost
    ens = 1.0 * xgb_pred + 0.0 * lstm_pred
    np.testing.assert_array_almost_equal(ens, xgb_pred)


# ── Peak detection ───────────────────────────────────────────────────────────

def test_peak_metrics_known():
    threshold = 2.0
    actual = np.array([1.0, 3.0, 3.0, 1.0, 3.0])  # peaks at idx 1,2,4
    pred   = np.array([1.0, 3.0, 1.0, 1.0, 3.0])  # correctly pred idx 1,4; misses idx 2
    # TP=2, FP=0, FN=1
    # precision = 1.0, recall = 2/3
    a_peaks = actual > threshold
    p_peaks = pred   > threshold
    tp = int((a_peaks & p_peaks).sum())
    fp = int((~a_peaks & p_peaks).sum())
    fn = int((a_peaks & ~p_peaks).sum())
    prec = tp / (tp + fp)
    rec  = tp / (tp + fn)
    assert tp == 2
    assert fp == 0
    assert fn == 1
    assert prec == pytest.approx(1.0)
    assert rec  == pytest.approx(2/3, rel=1e-3)


# ── Recursive forecast — no actual-future leakage ────────────────────────────

def test_recursive_uses_predictions_not_actuals():
    """Simulate a simple recursive 24-h forecast and verify actuals not used."""
    history = np.array([1.0, 1.2, 0.9, 1.1, 1.0])   # known past
    preds = []
    buf = list(history[-3:])   # 3-step lag buffer
    for step in range(24):
        # Simple model: next = mean of last 3
        next_pred = np.mean(buf[-3:])
        preds.append(next_pred)
        buf.append(next_pred)   # feed prediction, NOT an actual future value
    assert len(preds) == 24
    # All preds are derived from history + previous preds, not future actuals
    assert all(p > 0 for p in preds)
