import pytest
from pathlib import Path
from pyspark.sql import SparkSession
from pyspark.sql.types import StructType, StructField, TimestampType, DoubleType, StringType
import pyspark.sql.functions as F
import math

import os
import sys

# Ensure driver and worker use the exact same Python executable
os.environ["PYSPARK_PYTHON"] = sys.executable
os.environ["PYSPARK_DRIVER_PYTHON"] = sys.executable

sys.path.append(str(Path(__file__).parent.parent))

from src.feature_engineering import FeatureEngineer

@pytest.fixture(scope="session")
def spark():
    """Provides a SparkSession for testing."""
    spark = SparkSession.builder \
        .appName("TestFeatureEngineering") \
        .master("local[1]") \
        .config("spark.sql.session.timeZone", "UTC") \
        .getOrCreate()
    yield spark
    spark.stop()

@pytest.fixture
def mock_df(spark):
    """Creates a deterministic mock dataset for feature engineering."""
    schema = StructType([
        StructField("timestamp_str", StringType(), True),
        StructField("energy_kwh", DoubleType(), True)
    ])
    
    # Create 200 hours of continuous data starting from 2026-08-01 00:00:00 (Saturday)
    # This provides enough data to test lag_168
    data = []
    
    for i in range(200):
        # We will manually calculate datetime string
        day_offset = i // 24
        hour = i % 24
        day = 1 + day_offset
        ts = f"2026-08-{day:02d} {hour:02d}:00:00"
        
        # Make a deterministic energy pattern
        # Alternate 1.0, 2.0, 3.0
        energy = float((i % 3) + 1.0)
        data.append((ts, energy))
        
    df = spark.createDataFrame(data, schema)
    df = df.withColumn("timestamp", F.to_timestamp("timestamp_str", "yyyy-MM-dd HH:mm:ss")).drop("timestamp_str")
    return df

def test_calendar_features(spark, mock_df):
    engineer = FeatureEngineer(spark)
    df = engineer.create_calendar_features(mock_df)
    
    # 2026-08-01 15:00:00 is a Saturday
    row = df.filter(F.col("hour") == 15).filter(F.col("day") == 1).collect()[0]
    
    assert row["year"] == 2026
    assert row["month"] == 8
    assert row["day_of_month"] == 1
    assert row["hour"] == 15
    # Saturday should be 5
    assert row["day_of_week"] == 5
    assert row["is_weekend"] == 1
    
    # 2026-08-03 10:00:00 is Monday
    mon_row = df.filter(F.col("hour") == 10).filter(F.col("day") == 3).collect()[0]
    assert mon_row["day_of_week"] == 0
    assert mon_row["is_weekend"] == 0

def test_cyclical_features(spark, mock_df):
    engineer = FeatureEngineer(spark)
    df = engineer.create_calendar_features(mock_df)
    df = engineer.create_cyclical_features(df)
    
    row = df.filter(F.col("hour") == 6).collect()[0]
    
    # sin(2 * pi * 6 / 24) = sin(pi / 2) = 1.0
    assert math.isclose(row["hour_sin"], 1.0, rel_tol=1e-5)
    # cos(2 * pi * 6 / 24) = cos(pi / 2) = 0.0
    assert math.isclose(row["hour_cos"], 0.0, abs_tol=1e-5)

def test_lag_features(spark, mock_df):
    engineer = FeatureEngineer(spark)
    df = engineer.create_lag_features(mock_df, lags=[1, 24, 168])
    
    # Collect index 168 (169th row)
    rows = df.orderBy("timestamp").collect()
    
    # Index 0 has energy 1.0 (2026-08-01 00:00)
    # Index 1 has energy 2.0 (2026-08-01 01:00)
    # ...
    
    # At index 1, lag_1 should be index 0
    assert rows[1]["lag_1"] == rows[0]["energy_kwh"]
    
    # At index 24, lag_24 should be index 0
    assert rows[24]["lag_24"] == rows[0]["energy_kwh"]
    
    # At index 168, lag_168 should be index 0
    assert rows[168]["lag_168"] == rows[0]["energy_kwh"]

def test_rolling_features_no_leakage(spark, mock_df):
    engineer = FeatureEngineer(spark)
    df = engineer.create_rolling_features(mock_df, windows=[3])
    
    rows = df.orderBy("timestamp").collect()
    
    # idx 0: e=1.0
    # idx 1: e=2.0
    # idx 2: e=3.0
    # idx 3: e=1.0
    
    # For idx 3, rolling mean 3 should be average of idx 0, 1, 2 = (1+2+3)/3 = 2.0
    # It must NOT include idx 3 (value 1.0)
    assert rows[3]["rolling_mean_3"] == 2.0
    
def test_trend_features(spark, mock_df):
    engineer = FeatureEngineer(spark)
    df = engineer.create_lag_features(mock_df, lags=[1, 3, 24])
    df = engineer.create_trend_features(df)
    
    rows = df.orderBy("timestamp").collect()
    
    # At idx 3: lag_1 is idx 2 (e=3.0), lag_3 is idx 0 (e=1.0)
    # trend_3h = lag_1 - lag_3 = 3.0 - 1.0 = 2.0
    assert rows[3]["trend_3h"] == 2.0

def test_insufficient_history(spark, mock_df):
    engineer = FeatureEngineer(spark)
    df = engineer.create_lag_features(mock_df, lags=[1, 168])
    
    # Before drop, there should be 200 rows
    assert df.count() == 200
    
    df_clean = engineer.drop_insufficient_history(df, max_lag=168)
    
    # After dropping rows with null lag_168, the first 168 rows are gone
    # Remaining: 200 - 168 = 32
    assert df_clean.count() == 32
    
    # Verify no nulls in lag_168 remain
    assert df_clean.filter(F.col("lag_168").isNull()).count() == 0
