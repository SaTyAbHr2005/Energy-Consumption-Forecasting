import sys
import json
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
sys.path.append(str(project_root))

from src.spark_processor import SparkProcessor
import pyspark.sql.functions as F

def main():
    print("=" * 60)
    print("Spark Processing for Smart Home Energy Consumption")
    print("=" * 60)
    
    raw_data_path = project_root / 'data' / 'raw' / 'household_power_consumption.txt'
    if not raw_data_path.exists():
        print(f"Error: Raw dataset not found at {raw_data_path}")
        print("Please run scripts/download_dataset.py first.")
        sys.exit(1)
        
    metrics_dir = project_root / 'results' / 'metrics'
    metrics_dir.mkdir(parents=True, exist_ok=True)
    summary_path = metrics_dir / 'spark_processing_summary.json'
    
    processed_hourly_path = project_root / 'data' / 'processed' / 'uci_hourly'
    
    # Initialize processor
    print("Initializing SparkSession (local)...")
    processor = SparkProcessor()
    
    try:
        # Load data
        print("Loading UCI dataset with explicit schema...")
        df_raw = processor.load_uci_data(raw_data_path)
        
        # Calculate row count and partitions
        total_records = df_raw.count()
        num_partitions = df_raw.rdd.getNumPartitions()
        
        print(f"Records loaded: {total_records}")
        print(f"Number of partitions: {num_partitions}")
        print(f"Schema:")
        df_raw.printSchema()
        
        # Process data
        print("\nConstructing timestamps and calculating energy_kwh...")
        df_processed = processor.process_uci_data(df_raw)
        
        # Missing values analysis
        print("Performing missing value analysis...")
        numeric_cols = [
            "Global_active_power", "Global_reactive_power", "Voltage", 
            "Global_intensity", "Sub_metering_1", "Sub_metering_2", "Sub_metering_3"
        ]
        missing_stats = processor.calculate_missing_values(df_processed, numeric_cols)
        
        for k, v in missing_stats.items():
            print(f"  {k}: {v}")
            
        # Get timestamp boundaries
        print("\nCalculating timestamp boundaries...")
        bounds = df_processed.agg(
            F.min("timestamp").alias("start"),
            F.max("timestamp").alias("end")
        ).collect()[0]
        start_ts = str(bounds['start'])
        end_ts = str(bounds['end'])
        print(f"Start timestamp: {start_ts}")
        print(f"End timestamp:   {end_ts}")
        
        # Hourly aggregation
        print("\nAggregating to hourly resolution...")
        df_hourly = processor.aggregate_hourly(df_processed, is_uci=True)
        hourly_records = df_hourly.count()
        print(f"Hourly records generated: {hourly_records}")
        
        # Write to Parquet
        print(f"\nWriting processed hourly data to Parquet at {processed_hourly_path}...")
        processor.write_parquet(df_hourly, processed_hourly_path)
        print("Write completed successfully.")
        
        # Generate processing summary
        summary = {
            "dataset": "UCI Individual Household Electric Power Consumption",
            "records": total_records,
            "columns": len(df_raw.columns),
            "missing_values": missing_stats,
            "start_timestamp": start_ts,
            "end_timestamp": end_ts,
            "partitions": num_partitions,
            "hourly_records": hourly_records,
            "processing_status": "success"
        }
        
        with open(summary_path, 'w') as f:
            json.dump(summary, f, indent=4)
        print(f"\nProcessing summary saved to {summary_path}")
        
    except Exception as e:
        print(f"\nError during Spark processing: {e}")
    finally:
        print("\nStopping SparkSession...")
        processor.stop()
        print("Done.")

if __name__ == "__main__":
    main()
