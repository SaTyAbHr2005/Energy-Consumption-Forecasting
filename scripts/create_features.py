import sys
import os
import json
from pathlib import Path
import pandas as pd
from pyspark.sql import SparkSession
import pyspark.sql.functions as F

# Ensure driver and worker use the exact same Python executable
os.environ["PYSPARK_PYTHON"] = sys.executable
os.environ["PYSPARK_DRIVER_PYTHON"] = sys.executable

sys.path.append(str(Path(__file__).parent.parent))

from src.feature_engineering import FeatureEngineer

def save_parquet_safely(df, output_path: Path):
    """Safely saves Parquet, falling back to Pandas on Windows without Hadoop natives."""
    import shutil
    try:
        df.write.mode("overwrite").parquet(str(output_path))
    except Exception as e:
        error_str = str(e).lower()
        if "hadoop" in error_str or "winutils" in error_str:
            print("\n[WARNING] Spark Parquet write failed due to missing Hadoop native libraries.")
            print("[WARNING] Falling back to pandas to write to Parquet.")
            if output_path.exists() and output_path.is_dir():
                shutil.rmtree(output_path)
            pdf = df.toPandas()
            pdf.to_parquet(str(output_path), index=False, engine='pyarrow', coerce_timestamps='us', allow_truncated_timestamps=True)
        else:
            raise e

def main():
    print("=" * 60)
    print("FEATURE ENGINEERING PIPELINE")
    print("=" * 60)
    
    project_root = Path(__file__).parent.parent
    input_path = project_root / "data" / "processed" / "uci_hourly_clean.parquet"
    output_path = project_root / "data" / "processed" / "forecast_features.parquet"
    analytics_dir = project_root / "results" / "analytics"
    metrics_dir = project_root / "results" / "metrics"
    
    for d in [analytics_dir, metrics_dir]:
        d.mkdir(parents=True, exist_ok=True)
        
    print("Initializing SparkSession...")
    spark = SparkSession.builder \
        .appName("FeatureEngineering") \
        .master("local[*]") \
        .config("spark.sql.session.timeZone", "UTC") \
        .getOrCreate()
        
    try:
        print(f"Loading cleaned data from {input_path}...")
        df = spark.read.parquet(str(input_path))
        
        # Chronological ordering check (for safety)
        df = df.orderBy("timestamp")
        
        initial_count = df.count()
        print(f"Input records: {initial_count}")
        
        engineer = FeatureEngineer(spark)
        
        print("Creating calendar features...")
        df = engineer.create_calendar_features(df)
        
        print("Creating cyclical features...")
        df = engineer.create_cyclical_features(df)
        
        print("Creating lag features...")
        df = engineer.create_lag_features(df)
        
        print("Creating rolling features...")
        df = engineer.create_rolling_features(df)
        
        print("Creating trend features...")
        df = engineer.create_trend_features(df)
        
        print("Calculating contextual thresholds...")
        # Get 90th percentile from EDA/Current dataset
        p90_threshold = df.approxQuantile("energy_kwh", [0.90], 0.01)[0]
        print("Creating contextual features...")
        df = engineer.create_contextual_features(df, p90_threshold)
        
        # Calculate missing values BEFORE dropping burn-in
        null_counts = {col: df.filter(F.col(col).isNull()).count() for col in df.columns}
        missing_before = sum(null_counts.values())
        
        print("Dropping rows with insufficient history (burn-in period)...")
        df_final = engineer.drop_insufficient_history(df, max_lag=168)
        
        final_count = df_final.count()
        rows_removed = initial_count - final_count
        print(f"Rows removed for insufficient history: {rows_removed}")
        
        # Calculate missing values AFTER dropping burn-in
        final_null_counts = {col: df_final.filter(F.col(col).isNull()).count() for col in df_final.columns}
        missing_after = sum(final_null_counts.values())
        
        print("Calculating feature correlations...")
        target_features = [
            "energy_kwh", "lag_1", "lag_3", "lag_6", "lag_12", "lag_24", "lag_48", "lag_72", "lag_168",
            "rolling_mean_3", "rolling_mean_6", "rolling_mean_12", "rolling_mean_24", "rolling_mean_168"
        ]
        available_features = [f for f in target_features if f in df_final.columns]
        
        if available_features:
            pdf_corr = df_final.select(available_features).toPandas()
            corr_matrix = pdf_corr.corr()
            corr_matrix.to_csv(analytics_dir / "feature_correlations.csv")
            print(f"Correlations saved to {analytics_dir / 'feature_correlations.csv'}")
            
        print(f"Saving final dataset to {output_path}...")
        save_parquet_safely(df_final, output_path)
        
        feature_names = [c for c in df_final.columns if c not in ["timestamp", "energy_kwh"]]
        
        summary = {
            "input_records": initial_count,
            "output_records": final_count,
            "features_created": len(feature_names),
            "feature_names": feature_names,
            "rows_removed_for_history": rows_removed,
            "missing_values_before": missing_before,
            "missing_values_after": missing_after,
            "target_column": "energy_kwh"
        }
        
        with open(metrics_dir / "feature_summary.json", "w") as f:
            json.dump(summary, f, indent=4)
            
        print("=" * 50)
        print("FEATURE ENGINEERING SUMMARY")
        print("=" * 50)
        print(f"Input records: {initial_count}")
        print(f"Output records: {final_count}")
        print(f"\nTarget: energy_kwh")
        print(f"\nFeatures created: {len(feature_names)}")
        
        cat_calendar = [c for c in feature_names if c in ["year", "month", "day", "day_of_month", "day_of_week", "hour", "week_of_year", "quarter", "is_weekend"]]
        cat_cyclical = [c for c in feature_names if "sin" in c or "cos" in c]
        cat_lags = [c for c in feature_names if c.startswith("lag_")]
        cat_rolling = [c for c in feature_names if c.startswith("rolling_")]
        cat_trend = [c for c in feature_names if c.startswith("trend_")]
        
        print(f"\nCalendar features: {len(cat_calendar)}")
        print(f"Cyclical features: {len(cat_cyclical)}")
        print(f"Lag features: {len(cat_lags)}")
        print(f"Rolling features: {len(cat_rolling)}")
        print(f"Trend features: {len(cat_trend)}")
        
        print(f"\nRows removed for insufficient history: {rows_removed}")
        print(f"Final feature count: {len(feature_names)}")
        print(f"Remaining null values: {missing_after}")
        print(f"\nOutput:\n{output_path.relative_to(project_root)}")
        print("\nStatus: SUCCESS")
        print("=" * 50)
        
    except Exception as e:
        print(f"Error during feature engineering: {e}")
        import traceback
        traceback.print_exc()
    finally:
        spark.stop()

if __name__ == "__main__":
    main()
