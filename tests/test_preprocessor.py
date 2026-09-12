import pytest
from pathlib import Path
from pyspark.sql import SparkSession
import pyspark.sql.functions as F
from pyspark.sql.types import StructType, StructField, TimestampType, DoubleType, StringType
from datetime import datetime

import os
import sys

# Ensure driver and worker use the exact same Python executable
os.environ["PYSPARK_PYTHON"] = sys.executable
os.environ["PYSPARK_DRIVER_PYTHON"] = sys.executable

sys.path.append(str(Path(__file__).parent.parent))

from src.preprocessor import DataPreprocessor

@pytest.fixture(scope="session")
def spark():
    """Provides a SparkSession for testing."""
    spark = SparkSession.builder \
        .appName("TestPreprocessor") \
        .master("local[1]") \
        .config("spark.sql.session.timeZone", "UTC") \
        .getOrCreate()
    yield spark
    spark.stop()

@pytest.fixture
def mock_df(spark):
    """Creates a deterministic mock dataset with duplicates, gaps, and outliers."""
    schema = StructType([
        StructField("timestamp", TimestampType(), True),
        StructField("energy_kwh", DoubleType(), True),
        StructField("avg_voltage", DoubleType(), True)
    ])
    
    data = [
        # Normal data
        (datetime(2026, 1, 1, 0, 0, 0), 1.0, 240.0),
        (datetime(2026, 1, 1, 1, 0, 0), 2.0, 241.0),
        
        # Duplicate timestamp at 2:00
        (datetime(2026, 1, 1, 2, 0, 0), 1.5, 240.0),
        (datetime(2026, 1, 1, 2, 0, 0), 2.5, 242.0),
        
        # Short gap (3:00 missing)
        # Hour 3 is skipped
        
        # After short gap
        (datetime(2026, 1, 1, 4, 0, 0), 3.0, 239.0),
        
        # Long gap (5:00 to 9:00 missing)
        # Hours 5, 6, 7, 8 are skipped
        
        # After long gap
        (datetime(2026, 1, 1, 9, 0, 0), 1.5, 240.0),
        
        # Outlier
        (datetime(2026, 1, 1, 10, 0, 0), 50.0, 240.0),
        
        # Negative value
        (datetime(2026, 1, 1, 11, 0, 0), -5.0, 240.0)
    ]
    
    return spark.createDataFrame(data, schema)

def test_standardize_user_data(spark):
    """Test user schema conversion."""
    preprocessor = DataPreprocessor(spark)
    df = spark.createDataFrame([(datetime(2026, 1, 1), 5.0)], ["timestamp", "energy_consumption"])
    
    df_std = preprocessor.standardize_user_data(df)
    
    assert "energy_kwh" in df_std.columns
    assert "energy_consumption" not in df_std.columns
    assert df_std.collect()[0]["energy_kwh"] == 5.0

def test_validate_timestamps(spark):
    """Test min/max calculation and null removal."""
    preprocessor = DataPreprocessor(spark)
    schema = StructType([StructField("timestamp", TimestampType(), True)])
    data = [(datetime(2026, 1, 1, 0, 0, 0),), (None,), (datetime(2026, 1, 1, 2, 0, 0),)]
    df = spark.createDataFrame(data, schema)
    
    df_val = preprocessor.validate_timestamps(df)
    
    assert df_val.count() == 2
    assert preprocessor.report["null_timestamps_removed"] == 1
    assert "2026-01-01" in preprocessor.report["start_timestamp"]

def test_handle_duplicates(spark, mock_df):
    """Test duplicate timestamp aggregation."""
    preprocessor = DataPreprocessor(spark)
    df_dedup = preprocessor.handle_duplicates(mock_df)
    
    # We had 8 rows initially, with 1 pair of duplicates -> 7 unique rows
    assert df_dedup.count() == 7
    assert preprocessor.report["duplicate_timestamps"] == 1
    
    # Energy sum for duplicates: 1.5 + 2.5 = 4.0
    agg_row = df_dedup.filter(F.col("timestamp") == datetime(2026, 1, 1, 2, 0, 0)).collect()[0]
    assert agg_row["energy_kwh"] == 4.0
    
    # Avg for other columns: (240 + 242) / 2 = 241
    assert agg_row["avg_voltage"] == 241.0

def test_create_continuous_timeseries(spark, mock_df):
    """Test filling missing hourly periods."""
    preprocessor = DataPreprocessor(spark)
    df_dedup = preprocessor.handle_duplicates(mock_df)
    df_cont = preprocessor.create_continuous_timeseries(df_dedup)
    
    # Hours from 0 to 11 = 12 hours total
    assert df_cont.count() == 12
    assert preprocessor.report["expected_hourly_records"] == 12
    assert preprocessor.report["missing_hourly_records"] == 5

def test_full_preprocessing_pipeline(spark, mock_df, tmp_path):
    """Test full pipeline execution."""
    preprocessor = DataPreprocessor(spark)
    
    # Save mock data to temporary input path
    input_path = tmp_path / "input.parquet"
    mock_df.toPandas().to_parquet(str(input_path), index=False, engine='pyarrow', coerce_timestamps='us', allow_truncated_timestamps=True)
    
    output_path = tmp_path / "output_clean"
    
    df_clean = preprocessor.process(input_path, output_path)
    
    # Assertions
    # 12 total hours
    assert df_clean.count() == 12
    
    # Missing short gap interpolated?
    # Hour 2 energy = 4.0, Hour 4 energy = 3.0, Hour 3 should be 3.5
    row_h3 = df_clean.filter(F.col("timestamp") == datetime(2026, 1, 1, 3, 0, 0)).collect()[0]
    assert row_h3["energy_kwh"] == 3.5
    
    # Long gap not interpolated?
    row_h5 = df_clean.filter(F.col("timestamp") == datetime(2026, 1, 1, 5, 0, 0)).collect()[0]
    assert row_h5["energy_kwh"] is None
    assert row_h5["is_long_gap"] == 1
    
    # Outlier detection
    row_h10 = df_clean.filter(F.col("timestamp") == datetime(2026, 1, 1, 10, 0, 0)).collect()[0]
    assert row_h10["is_energy_outlier"] == 1
    
    # Negative floored
    row_h11 = df_clean.filter(F.col("timestamp") == datetime(2026, 1, 1, 11, 0, 0)).collect()[0]
    assert row_h11["energy_kwh"] == 0.0

    # Ensure output exists
    assert Path(str(output_path)).exists() or Path(str(output_path) + ".parquet").exists()
