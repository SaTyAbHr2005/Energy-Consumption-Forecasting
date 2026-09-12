import sys
import os
import json
from pathlib import Path
from pyspark.sql import SparkSession

# Ensure driver and worker use the exact same Python executable
os.environ["PYSPARK_PYTHON"] = sys.executable
os.environ["PYSPARK_DRIVER_PYTHON"] = sys.executable

# Add the project root to Python path
sys.path.append(str(Path(__file__).parent.parent))

from src.preprocessor import DataPreprocessor

def main():
    print("=" * 60)
    print("Data Preprocessing for Smart Home Energy Consumption")
    print("=" * 60)
    
    project_root = Path(__file__).parent.parent
    input_path = project_root / "data" / "processed" / "uci_hourly"
    output_path = project_root / "data" / "processed" / "uci_hourly_clean"
    metrics_path = project_root / "results" / "metrics" / "preprocessing_summary.json"
    
    # Ensure directories exist
    output_path.parent.mkdir(parents=True, exist_ok=True)
    metrics_path.parent.mkdir(parents=True, exist_ok=True)
    
    print("Initializing SparkSession (local)...")
    spark = SparkSession.builder \
        .appName("EnergyDataPreprocessing") \
        .master("local[*]") \
        .config("spark.sql.session.timeZone", "UTC") \
        .getOrCreate()
        
    try:
        print(f"Loading data from {input_path}...")
        preprocessor = DataPreprocessor(spark)
        
        df_clean = preprocessor.process(input_path, output_path)
        
        print("\nSaving preprocessing report...")
        with open(metrics_path, "w") as f:
            json.dump(preprocessor.report, f, indent=4)
            
        print(f"\nPreprocessing summary:")
        print(f"  Input records: {preprocessor.report.get('input_records')}")
        print(f"  Null timestamps removed: {preprocessor.report.get('null_timestamps_removed')}")
        print(f"  Duplicate timestamps: {preprocessor.report.get('duplicate_timestamps')}")
        print(f"  Missing hourly records filled: {preprocessor.report.get('missing_hourly_records')}")
        print(f"  Outliers detected: {preprocessor.report.get('outlier_count')}")
        print(f"  Final output records: {preprocessor.report.get('output_records')}")
        
        missing_before = preprocessor.report.get("missing_values_before", {})
        missing_after = preprocessor.report.get("missing_values_after", {})
        
        print(f"\nMissing values before -> after:")
        for k in missing_before:
            print(f"  {k}: {missing_before[k]} -> {missing_after.get(k, 0)}")
            
        print(f"\nCleaned dataset saved to {output_path}")
        print(f"Report saved to {metrics_path}")
        
    except Exception as e:
        print(f"\nError during preprocessing: {str(e)}")
        import traceback
        traceback.print_exc()
    finally:
        print("\nStopping SparkSession...")
        spark.stop()
        print("Done.")

if __name__ == "__main__":
    main()
