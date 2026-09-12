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

from src.eda import EnergyDataAnalyzer

@pytest.fixture(scope="session")
def spark():
    """Provides a SparkSession for testing."""
    spark = SparkSession.builder \
        .appName("TestEDA") \
        .master("local[1]") \
        .config("spark.sql.session.timeZone", "UTC") \
        .getOrCreate()
    yield spark
    spark.stop()

@pytest.fixture
def mock_df(spark):
    """Creates a deterministic mock dataset for EDA."""
    schema = StructType([
        StructField("timestamp_str", StringType(), True),
        StructField("energy_kwh", DoubleType(), True),
        StructField("total_sub_metering_1", DoubleType(), True),
        StructField("total_sub_metering_2", DoubleType(), True),
        StructField("total_sub_metering_3", DoubleType(), True)
    ])
    
    # 2026-08-01 is a Saturday
    data = [
        ("2026-08-01 10:00:00", 2.0, 0.5, 0.5, 1.0), # Saturday
        ("2026-08-01 20:00:00", 4.0, 1.0, 1.0, 2.0), # Saturday Peak
        ("2026-08-02 10:00:00", 1.5, 0.5, 0.0, 1.0), # Sunday
        ("2026-08-03 02:00:00", 0.5, 0.0, 0.0, 0.5), # Monday Low
        ("2026-08-03 10:00:00", 1.0, 0.0, 0.0, 1.0), # Monday
        ("2026-08-03 18:00:00", 3.0, 1.0, 0.5, 1.5), # Monday Peak
    ]
    
    df = spark.createDataFrame(data, schema)
    return df.withColumn("timestamp", F.to_timestamp("timestamp_str", "yyyy-MM-dd HH:mm:ss")).drop("timestamp_str")

def test_dataset_statistics(spark, mock_df):
    analyzer = EnergyDataAnalyzer(spark)
    stats = analyzer.calculate_dataset_statistics(mock_df)
    
    assert stats["num_records"] == 6
    assert stats["num_variables"] == 5
    assert stats["energy_kwh_stats"]["max"] == 4.0
    assert stats["energy_kwh_stats"]["min"] == 0.5
    # mean = (2 + 4 + 1.5 + 0.5 + 1 + 3) / 6 = 12 / 6 = 2.0
    assert stats["energy_kwh_stats"]["mean"] == 2.0

def test_temporal_features(spark, mock_df):
    analyzer = EnergyDataAnalyzer(spark)
    df_enriched = analyzer.enrich_with_temporal_features(mock_df)
    
    cols = df_enriched.columns
    assert "hour" in cols
    assert "dayofweek_num" in cols
    assert "day_name" in cols
    assert "month" in cols
    assert "is_weekend" in cols
    assert "season" in cols
    
    # Test Saturday
    sat_row = df_enriched.filter(F.col("day_name") == "Saturday").collect()[0]
    assert sat_row["is_weekend"] == 1
    
    # Test Monday
    mon_row = df_enriched.filter(F.col("day_name") == "Monday").collect()[0]
    assert mon_row["is_weekend"] == 0

def test_hourly_patterns(spark, mock_df):
    analyzer = EnergyDataAnalyzer(spark)
    df_enriched = analyzer.enrich_with_temporal_features(mock_df)
    hourly = analyzer.calculate_hourly_patterns(df_enriched).collect()
    
    # Hour 10: (2.0 + 1.5 + 1.0) / 3 = 1.5
    h10 = [r for r in hourly if r["hour"] == 10][0]
    assert h10["avg_energy_kwh"] == 1.5

def test_daily_patterns(spark, mock_df):
    analyzer = EnergyDataAnalyzer(spark)
    df_enriched = analyzer.enrich_with_temporal_features(mock_df)
    daily = analyzer.calculate_daily_patterns(df_enriched).collect()
    
    assert len(daily) == 3 # Aug 1, Aug 2, Aug 3
    
    # Check total for the day that had 6.0 total
    totals = [r["total_energy_kwh"] for r in daily]
    assert 6.0 in totals

def test_weekday_weekend(spark, mock_df):
    analyzer = EnergyDataAnalyzer(spark)
    df_enriched = analyzer.enrich_with_temporal_features(mock_df)
    comp = analyzer.calculate_weekday_weekend_comparison(df_enriched)
    
    # Weekend total = 2.0 + 4.0 + 1.5 = 7.5
    # Weekday total = 0.5 + 1.0 + 3.0 = 4.5
    assert comp["weekend"]["total"] == 7.5
    assert comp["weekday"]["total"] == 4.5

def test_peak_demand(spark, mock_df):
    analyzer = EnergyDataAnalyzer(spark)
    
    # p90=3.5, p95=3.8 -> 4.0 is critical, 3.0 is normal, 1.0 is normal
    df_demand = analyzer.analyze_peak_demand(mock_df, 3.5, 3.8)
    
    critical = df_demand.filter(F.col("demand_level") == "critical").count()
    high = df_demand.filter(F.col("demand_level") == "high").count()
    
    assert critical == 1 # The 4.0 value
    assert high == 0

def test_submetering(spark, mock_df):
    analyzer = EnergyDataAnalyzer(spark)
    sub = analyzer.analyze_submetering(mock_df)
    
    # sm1 total = 0.5 + 1.0 + 0.5 + 0.0 + 0.0 + 1.0 = 3.0
    assert sub["sub_metering_1"]["total"] == 3.0
    
    # sum of all sm = sm1(3.0) + sm2(2.0) + sm3(7.0) = 12.0
    assert sub["sub_metering_1"]["relative_contribution"] == 3.0 / 12.0

def test_variability(spark, mock_df):
    analyzer = EnergyDataAnalyzer(spark)
    df_enriched = analyzer.enrich_with_temporal_features(mock_df)
    var = analyzer.analyze_variability(df_enriched)
    
    assert var["overall_cv"] is not None
    assert var["overall_stddev"] is not None
    assert 10 in var["hourly_stddev"] # Hour 10 exists

def test_autocorrelation(spark, mock_df):
    analyzer = EnergyDataAnalyzer(spark)
    # Autocorrelation needs sufficient data, with 6 rows lag 1 might be computable
    ac = analyzer.calculate_autocorrelation(mock_df)
    
    assert "lag_1" in ac
    assert "lag_24" in ac
