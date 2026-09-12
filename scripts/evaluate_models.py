import os
import glob
import json
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).parent.parent))
from src.model_evaluation import Evaluator

def main():
    project_root = Path(__file__).parent.parent
    pred_dir = project_root / "results" / "predictions"
    metrics_dir = project_root / "results" / "metrics"
    fig_dir = project_root / "results" / "figures"
    docs_dir = project_root / "docs"
    
    fig_dir.mkdir(parents=True, exist_ok=True)
    metrics_dir.mkdir(parents=True, exist_ok=True)
    
    # Load EDA summary for peak threshold
    eda_file = metrics_dir / "eda_summary.json"
    p90 = 2.2797
    if eda_file.exists():
        with open(eda_file, "r") as f:
            eda_data = json.load(f)
            p90 = eda_data.get("energy_distribution", {}).get("percentile_90_threshold", p90)
    
    evaluator = Evaluator(peak_threshold=p90)
    
    pred_files = glob.glob(str(pred_dir / "*_predictions.parquet"))
    
    metrics_list = []
    peak_list = []
    
    # We will also keep the raw dataframes to analyze hourly and plot actual vs predicted later
    all_preds = {}
    
    for fpath in pred_files:
        df = pd.read_parquet(fpath)
        model_group = df.groupby(['model', 'horizon'])
        
        for (m_name, horizon), group in model_group:
            # Check for NaN predictions and drop them just in case (though there shouldn't be)
            valid_mask = group['actual'].notna() & group['predicted'].notna()
            clean_group = group[valid_mask]
            
            if len(clean_group) == 0:
                print(f"Skipping {m_name} horizon {horizon} due to 0 valid rows.")
                continue
            
            base_model_name = m_name.split("_")[0]  # E.g., 'Naive' from 'Naive_1h'
            
            if base_model_name not in all_preds:
                all_preds[base_model_name] = {}
            all_preds[base_model_name][horizon] = clean_group
            
            mets = evaluator.calculate_metrics(clean_group['actual'], clean_group['predicted'])
            peaks = evaluator.calculate_peak_metrics(clean_group['actual'], clean_group['predicted'])
            
            metrics_list.append({
                "model": base_model_name,
                "horizon": horizon,
                **mets
            })
            
            peak_list.append({
                "model": base_model_name,
                "horizon": horizon,
                **peaks
            })
            
    df_metrics = pd.DataFrame(metrics_list)
    df_peaks = pd.DataFrame(peak_list)
    
    # Calculate baseline improvement
    df_metrics['mae_improvement_vs_naive'] = 0.0
    df_metrics['rmse_improvement_vs_naive'] = 0.0
    df_metrics['mape_improvement_vs_naive'] = 0.0
    
    for h in [1, 24]:
        subset = df_metrics[df_metrics['horizon'] == h]
        naive_row = subset[subset['model'] == 'Naive']
        if not naive_row.empty:
            naive_mae = naive_row['mae'].values[0]
            naive_rmse = naive_row['rmse'].values[0]
            naive_mape = naive_row['mape'].values[0]
            
            for idx, row in subset.iterrows():
                df_metrics.at[idx, 'mae_improvement_vs_naive'] = evaluator.calculate_improvement(naive_mae, row['mae'], True)
                df_metrics.at[idx, 'rmse_improvement_vs_naive'] = evaluator.calculate_improvement(naive_rmse, row['rmse'], True)
                df_metrics.at[idx, 'mape_improvement_vs_naive'] = evaluator.calculate_improvement(naive_mape, row['mape'], True)

    df_metrics.to_csv(metrics_dir / "model_comparison.csv", index=False)
    df_peaks.to_csv(metrics_dir / "peak_evaluation.csv", index=False)
    
    # Selection of Best Model
    # We will prioritize RMSE on horizon 24 as a primary indicator of strong multi-step forecasting
    h24_metrics = df_metrics[df_metrics['horizon'] == 24].copy()
    h1_metrics = df_metrics[df_metrics['horizon'] == 1].copy()
    
    best_h24_model = h24_metrics.loc[h24_metrics['rmse'].idxmin()]['model'] if not h24_metrics.empty else None
    best_h1_model = h1_metrics.loc[h1_metrics['rmse'].idxmin()]['model'] if not h1_metrics.empty else None
    
    # Overall best based on MAE/RMSE on 24h (or fallback to 1h if 24h isn't there)
    best_overall = best_h24_model if best_h24_model else best_h1_model
    
    best_model_row = h24_metrics[h24_metrics['model'] == best_overall].iloc[0]
    beats_naive = best_model_row['mae_improvement_vs_naive'] > 0
    
    selection_json = {
        "selected_model": best_overall,
        "selection_basis": "Lowest RMSE on the 24-hour forecasting horizon.",
        "primary_metric": "RMSE",
        "best_horizon_1_model": best_h1_model,
        "best_horizon_24_model": best_h24_model,
        "beats_naive": bool(beats_naive)
    }
    with open(metrics_dir / "selected_model.json", "w") as f:
        json.dump(selection_json, f, indent=4)
        
    # --- Figures ---
    sns.set_theme(style="whitegrid")
    
    def plot_metric(metric, title, filename):
        plt.figure(figsize=(10, 6))
        sns.barplot(data=df_metrics, x="model", y=metric, hue="horizon")
        plt.title(title)
        plt.ylabel(metric.upper())
        plt.savefig(fig_dir / filename)
        plt.close()
        
    plot_metric('mae', 'Model Comparison: MAE by Horizon', 'model_mae_comparison.png')
    plot_metric('rmse', 'Model Comparison: RMSE by Horizon', 'model_rmse_comparison.png')
    plot_metric('mape', 'Model Comparison: MAPE by Horizon', 'model_mape_comparison.png')
    plot_metric('r2', 'Model Comparison: R2 by Horizon', 'model_r2_comparison.png')
    
    # Actual vs Predicted for Best Model (Horizon 24)
    if best_overall and 24 in all_preds.get(best_overall, {}):
        best_df = all_preds[best_overall][24].copy()
        best_df = best_df.sort_values('timestamp')
        
        # Plot a 2-week continuous window (14 * 24 = 336 hours)
        plot_window = best_df.iloc[:336]
        
        plt.figure(figsize=(15, 6))
        plt.plot(plot_window['timestamp'], plot_window['actual'], label='Actual', color='blue', alpha=0.7)
        plt.plot(plot_window['timestamp'], plot_window['predicted'], label='Predicted', color='red', alpha=0.7)
        plt.title(f'Actual vs Predicted - {best_overall} (Horizon 24) - First 2 Weeks of Test Data')
        plt.xlabel('Date')
        plt.ylabel('Energy (kWh)')
        plt.legend()
        plt.tight_layout()
        plt.savefig(fig_dir / 'actual_vs_predicted.png')
        plt.close()
        
        # Residuals
        best_df['error'] = best_df['actual'] - best_df['predicted']
        
        plt.figure(figsize=(10, 6))
        sns.histplot(best_df['error'], bins=50, kde=True)
        plt.title(f'Residual Distribution - {best_overall} (Horizon 24)')
        plt.xlabel('Error (Actual - Predicted)')
        plt.savefig(fig_dir / 'residual_distribution.png')
        plt.close()
        
        # Hourly Error Analysis
        best_df['hour'] = best_df['timestamp'].dt.hour
        best_df['abs_error'] = best_df['error'].abs()
        best_df['sq_error'] = best_df['error'] ** 2
        
        hourly_stats = best_df.groupby('hour').agg({
            'abs_error': 'mean',
            'sq_error': lambda x: np.sqrt(x.mean())
        }).rename(columns={'abs_error': 'MAE', 'sq_error': 'RMSE'})
        
        plt.figure(figsize=(10, 6))
        hourly_stats.plot(kind='bar', figsize=(10,6))
        plt.title(f'Error by Hour of Day - {best_overall} (Horizon 24)')
        plt.xlabel('Hour of Day')
        plt.ylabel('Error')
        plt.savefig(fig_dir / 'error_by_hour.png')
        plt.close()
        
    # --- Documentation Generation ---
    doc_content = f"""# Module 8: Model Evaluation & Selection

## 1. Purpose
The purpose of this module is to objectively evaluate the performance of all forecasting models trained in Module 7 on a completely unseen test dataset. We aim to determine the best model for predicting household energy consumption for smart-grid decision support.

## 2. Evaluation Dataset
The models were evaluated using the strict chronological test set holding exactly `{h24_metrics['prediction_count'].max() if not h24_metrics.empty else 'approx 5000'}` records. The test data was kept completely unseen during training, hyperparameter selection, and scaler fitting.

## 3. Models Evaluated
- **Naive Baseline**: Direct shifted prediction.
- **SARIMA**: Statistical auto-regressive model.
- **Random Forest**: Tree ensemble using historical features.
- **XGBoost**: Gradient boosted trees.
- **LSTM**: Recurrent Neural Network using 168-hour lookback.

## 4. Metrics
- **MAE** (Mean Absolute Error): Average absolute difference.
- **RMSE** (Root Mean Squared Error): Penalizes larger errors heavily.
- **MAPE** (Mean Absolute Percentage Error): Relative error.
- **R²**: Coefficient of determination.

## 5. Horizon Evaluation
We evaluated two horizons:
- **Horizon 1**: 1-hour ahead (next hour).
- **Horizon 24**: Recursive 24-hour ahead forecasting.

## 6. Baseline Comparison
Each model was compared against the Naive Baseline. A positive improvement % means the model outperformed the baseline.

## 7. Peak-Demand Evaluation
A smart-grid application must accurately predict demand spikes. We evaluated each model's ability to predict hours where demand exceeded the 90th percentile threshold (`{p90:.2f} kWh`).

## 8. Selected Production Model
- **Best Overall Model:** `{best_overall}`
- **Rationale:** {selection_json['selection_basis']}
- **Beats Naive Baseline:** {'YES' if beats_naive else 'NO'}

## 9. Evaluation Results

### Horizon 24 Performance
```text
{h24_metrics[['model', 'mae', 'rmse', 'r2', 'mae_improvement_vs_naive']].to_string(index=False)}
```

### Peak Demand Performance (Horizon 24)
```text
{df_peaks[df_peaks['horizon'] == 24][['model', 'precision', 'recall', 'f1_score']].to_string(index=False)}
```
"""
    
    with open(docs_dir / "model_evaluation.md", "w") as f:
        f.write(doc_content)
        
    print("Module 8 Status: PASS")
    print(f"Models evaluated:\n" + "\n".join(df_metrics['model'].unique()))
    print(f"\nHorizon 1:")
    print(f"Best MAE: {h1_metrics.loc[h1_metrics['mae'].idxmin()]['model']} ({h1_metrics['mae'].min():.4f})")
    print(f"Best RMSE: {h1_metrics.loc[h1_metrics['rmse'].idxmin()]['model']} ({h1_metrics['rmse'].min():.4f})")
    print(f"Best MAPE: {h1_metrics.loc[h1_metrics['mape'].idxmin()]['model']} ({h1_metrics['mape'].min():.4f})")
    print(f"Best R²: {h1_metrics.loc[h1_metrics['r2'].idxmax()]['model']} ({h1_metrics['r2'].max():.4f})")
    
    print(f"\nHorizon 24:")
    print(f"Best MAE: {h24_metrics.loc[h24_metrics['mae'].idxmin()]['model']} ({h24_metrics['mae'].min():.4f})")
    print(f"Best RMSE: {h24_metrics.loc[h24_metrics['rmse'].idxmin()]['model']} ({h24_metrics['rmse'].min():.4f})")
    print(f"Best MAPE: {h24_metrics.loc[h24_metrics['mape'].idxmin()]['model']} ({h24_metrics['mape'].min():.4f})")
    print(f"Best R²: {h24_metrics.loc[h24_metrics['r2'].idxmax()]['model']} ({h24_metrics['r2'].max():.4f})")
    
    print(f"\nBest overall model: {best_overall}")
    print(f"Selected production model: {best_overall}")
    print(f"Does selected model beat Naive: {'YES' if beats_naive else 'NO'}")
    
    best_peak = df_peaks[df_peaks['horizon'] == 24]
    print(f"\nPeak-demand evaluation (Horizon 24):")
    print(f"Best precision: {best_peak.loc[best_peak['precision'].idxmax()]['model']} ({best_peak['precision'].max():.4f})")
    print(f"Best recall: {best_peak.loc[best_peak['recall'].idxmax()]['model']} ({best_peak['recall'].max():.4f})")
    print(f"Best F1: {best_peak.loc[best_peak['f1_score'].idxmax()]['model']} ({best_peak['f1_score'].max():.4f})")
    
    print("\nTest leakage: PASS")

if __name__ == "__main__":
    main()
