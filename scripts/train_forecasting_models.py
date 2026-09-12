import sys
import json
from pathlib import Path
import pandas as pd
import numpy as np

sys.path.append(str(Path(__file__).parent.parent))

from src.forecasting import DataSplitter, NaiveForecaster, SARIMAModelWrapper, TreeForecaster, LSTMForecaster

def main():
    print("=" * 50)
    print("FORECASTING MODELS TRAINING PIPELINE (MODULE 7)")
    print("=" * 50)
    
    project_root = Path(__file__).parent.parent
    data_path = project_root / "data" / "processed" / "forecast_features.parquet"
    models_dir = project_root / "models"
    metrics_dir = project_root / "results" / "metrics"
    predictions_dir = project_root / "results" / "predictions"
    figures_dir = project_root / "results" / "figures"
    
    for d in [models_dir, metrics_dir, predictions_dir, figures_dir]:
        d.mkdir(parents=True, exist_ok=True)
        
    print(f"Loading feature dataset from {data_path}...")
    df = pd.read_parquet(data_path)
    
    # Pre-flight Audit
    print("Performing Pre-Flight Audit...")
    assert df['timestamp'].is_monotonic_increasing, "Chronological ordering failed!"
    assert df.isnull().sum().sum() == 0, "Missing values found in feature dataset!"
    
    # Chronological Split
    print("Performing Chronological Split (70/15/15)...")
    train_df, val_df, test_df = DataSplitter.chronological_split(df)
    
    total_records = len(df)
    print(f"Total records: {total_records}")
    print(f"Train records: {len(train_df)}")
    print(f"Validation records: {len(val_df)}")
    print(f"Test records: {len(test_df)}")
    
    split_info = {
        "total_records": total_records,
        "train_records": len(train_df),
        "validation_records": len(val_df),
        "test_records": len(test_df),
        "train_start": str(train_df['timestamp'].min()),
        "train_end": str(train_df['timestamp'].max()),
        "validation_start": str(val_df['timestamp'].min()),
        "validation_end": str(val_df['timestamp'].max()),
        "test_start": str(test_df['timestamp'].min()),
        "test_end": str(test_df['timestamp'].max())
    }
    with open(metrics_dir / "data_split.json", "w") as f:
        json.dump(split_info, f, indent=4)
        
    
    excluded_cols = [
        'timestamp', 'energy_kwh', 
        'avg_global_active_power', 'avg_global_reactive_power', 
        'avg_voltage', 'avg_global_intensity', 
        'total_sub_metering_1', 'total_sub_metering_2', 'total_sub_metering_3',
        'is_long_gap', 'is_energy_outlier'
    ]
    feature_cols = [c for c in df.columns if c not in excluded_cols]
    p90 = df['energy_kwh'].quantile(0.90)
    
    with open(metrics_dir / "model_features.json", "w") as f:
        json.dump({"features": feature_cols}, f, indent=4)
        
    # --- NAIVE BASELINE ---
    print("\n[1/5] Running Naive Baseline...")
    naive = NaiveForecaster()
    naive_1h = naive.predict_1h(test_df)
    naive_24h = naive.predict_24h(test_df)
    naive_preds = pd.concat([naive_1h, naive_24h], ignore_index=True)
    naive_preds.to_parquet(predictions_dir / "naive_predictions.parquet", index=False)
    
    # --- SARIMA ---
    print("[2/5] Training SARIMA...")
    # Keep it lightweight to ensure it runs: (1,0,0)(1,0,0,24).
    # Fit only on the last small portion of training to avoid hours of execution, OR use lightweight args.
    # Statsmodels SARIMAX over 20k rows is extremely slow. We will fit on last 2 weeks of training data.
    train_recent = train_df.iloc[-336:]['energy_kwh']
    sarima = SARIMAModelWrapper(order=(1,0,0), seasonal_order=(1,0,0,24))
    sarima.fit(train_recent)
    sarima_1h = sarima.predict_1h(test_df, train_df['energy_kwh'])
    
    # SARIMA 24h recursive for the LAST 24 hours of the test set
    sarima_24h_vals = sarima.forecast_24h(steps=24)
    future_timestamps = test_df['timestamp'].iloc[-24:].tolist()
    sarima_24h = pd.DataFrame({
        'timestamp': future_timestamps,
        'actual': test_df['energy_kwh'].iloc[-24:].tolist(),
        'predicted': sarima_24h_vals,
        'horizon': [24] * 24,
        'model': 'SARIMA_24h'
    })
    sarima_preds = pd.concat([sarima_1h, sarima_24h], ignore_index=True)
    sarima_preds.to_parquet(predictions_dir / "sarima_predictions.parquet", index=False)

    # --- RANDOM FOREST ---
    print("[3/5] Training Random Forest...")
    rf = TreeForecaster(model_type='rf', n_estimators=50, random_state=42, n_jobs=-1)
    rf.fit(train_df, train_df['energy_kwh'], p90, feature_cols)
    rf_1h = rf.predict_1h(test_df)
    
    test_history_rf = test_df.iloc[:-24]
    rf_24h = rf.predict_24h_recursive(test_history_rf, test_df['timestamp'].iloc[-24], steps=24)
    rf_24h['actual'] = test_df['energy_kwh'].iloc[-24:].values
    rf_24h['horizon'] = 24
    rf_preds = pd.concat([rf_1h, rf_24h], ignore_index=True)
    rf_preds.to_parquet(predictions_dir / "random_forest_predictions.parquet", index=False)
    
    # --- XGBOOST ---
    print("[4/5] Training XGBoost...")
    xgb = TreeForecaster(model_type='xgb', n_estimators=100, learning_rate=0.1, random_state=42, n_jobs=-1)
    xgb.fit(train_df, train_df['energy_kwh'], p90, feature_cols)
    xgb_1h = xgb.predict_1h(test_df)
    
    test_history_xgb = test_df.iloc[:-24]
    xgb_24h = xgb.predict_24h_recursive(test_history_xgb, test_df['timestamp'].iloc[-24], steps=24)
    xgb_24h['actual'] = test_df['energy_kwh'].iloc[-24:].values
    xgb_24h['horizon'] = 24
    xgb_preds = pd.concat([xgb_1h, xgb_24h], ignore_index=True)
    xgb_preds.to_parquet(predictions_dir / "xgboost_predictions.parquet", index=False)
    
    # --- LSTM ---
    print("[5/5] Training LSTM...")
    lstm = LSTMForecaster(seq_length=168, epochs=3, batch_size=128)
    lstm.fit(train_df['energy_kwh'], val_df['energy_kwh'])
    
    # To predict test_df 1h, we need val_df's last 168 rows + test_df
    combined_test = pd.concat([val_df.iloc[-168:], test_df])
    lstm_1h = lstm.predict_1h(combined_test['energy_kwh'], combined_test['timestamp'])
    
    lstm_history = combined_test.iloc[:-24]
    lstm_24h = lstm.predict_24h_recursive(lstm_history['energy_kwh'].iloc[-168:], test_df['timestamp'].iloc[-24], steps=24)
    lstm_24h['actual'] = test_df['energy_kwh'].iloc[-24:].values
    lstm_24h['horizon'] = 24
    lstm_preds = pd.concat([lstm_1h, lstm_24h], ignore_index=True)
    lstm_preds.to_parquet(predictions_dir / "lstm_predictions.parquet", index=False)
    
    # Save LSTM history plot
    try:
        import matplotlib.pyplot as plt
        plt.figure(figsize=(10, 6))
        plt.plot(lstm.history.history['loss'], label='Train Loss')
        plt.plot(lstm.history.history['val_loss'], label='Val Loss')
        plt.title('LSTM Training History')
        plt.xlabel('Epoch')
        plt.ylabel('MSE Loss')
        plt.legend()
        plt.savefig(figures_dir / "lstm_training_loss.png")
        plt.close()
    except Exception as e:
        print(f"Warning: Could not plot LSTM history: {e}")

    # Summary
    summary = {
        "models": ["Naive", "SARIMA", "RandomForest", "XGBoost", "LSTM"],
        "training_records": len(train_df),
        "validation_records": len(val_df),
        "test_records": len(test_df),
        "training_start": str(train_df['timestamp'].min()),
        "training_end": str(train_df['timestamp'].max()),
        "validation_start": str(val_df['timestamp'].min()),
        "validation_end": str(val_df['timestamp'].max()),
        "test_start": str(test_df['timestamp'].min()),
        "test_end": str(test_df['timestamp'].max()),
        "forecast_horizons": [1, 24],
        "training_status": "SUCCESS",
        "sarima_config": {"order": [1,0,0], "seasonal_order": [1,0,0,24]},
        "lstm_config": {"sequence_length": 168, "epochs": 3, "batch_size": 128}
    }
    with open(metrics_dir / "training_summary.json", "w") as f:
        json.dump(summary, f, indent=4)
        
    print("\n" + "=" * 50)
    print("MODULE 7 STATUS: SUCCESS")
    print("Predictions saved to results/predictions/")
    print("=" * 50)

if __name__ == "__main__":
    main()
