import pytest
from pathlib import Path
import sys

project_root = Path(__file__).resolve().parent.parent
sys.path.append(str(project_root))

from src.spark_processor import SparkProcessor

FIXTURES_DIR = Path(__file__).parent / 'fixtures'

@pytest.fixture(scope="module")
def spark_proc():
    processor = SparkProcessor(app_name="TestSparkProcessing")
    yield processor
    processor.stop()

@pytest.fixture(scope="module")
def small_uci_file(tmp_path_factory):
    content = """Date;Time;Global_active_power;Global_reactive_power;Voltage;Global_intensity;Sub_metering_1;Sub_metering_2;Sub_metering_3
16/12/2006;17:24:00;4.216;0.418;234.840;18.400;0.000;1.000;17.000
16/12/2006;17:25:00;5.360;0.436;233.630;23.000;0.000;1.000;16.000
16/12/2006;17:26:00;?;0.498;233.290;23.000;0.000;2.000;17.000
"""
    fn = tmp_path_factory.mktemp("data") / "small_uci_test.csv"
    fn.write_text(content)
    return fn
    
@pytest.fixture(scope="module")
def small_user_file(tmp_path_factory):
    content = """timestamp,energy_consumption
2026-08-01 00:00:00,0.42
2026-08-01 00:15:00,0.38
2026-08-01 01:00:00,0.35
"""
    fn = tmp_path_factory.mktemp("data") / "small_user_test.csv"
    fn.write_text(content)
    return fn

def test_load_uci_and_process(spark_proc, small_uci_file):
    df_raw = spark_proc.load_uci_data(small_uci_file)
    assert df_raw.count() == 3
    
    df_processed = spark_proc.process_uci_data(df_raw)
    
    # Check if timestamp exists and energy_kwh is calculated
    cols = df_processed.columns
    assert "timestamp" in cols
    assert "energy_kwh" in cols
    
    # Check missing values
    numeric_cols = ["Global_active_power"]
    missing = spark_proc.calculate_missing_values(df_processed, numeric_cols)
    assert missing["missing_Global_active_power"] == 1
    
    # Check energy conversion: 4.216 / 60 = 0.070266...
    first_row = df_processed.filter(df_processed.Time == "17:24:00").collect()[0]
    assert abs(first_row["energy_kwh"] - (4.216 / 60.0)) < 1e-6

def test_hourly_aggregation(spark_proc, small_uci_file):
    df_raw = spark_proc.load_uci_data(small_uci_file)
    df_processed = spark_proc.process_uci_data(df_raw)
    
    df_hourly = spark_proc.aggregate_hourly(df_processed, is_uci=True)
    assert df_hourly.count() == 1 # all in 17:00 hour
    row = df_hourly.collect()[0]
    assert "energy_kwh" in df_hourly.columns
    assert "avg_global_active_power" in df_hourly.columns

def test_user_csv_processing(spark_proc, small_user_file):
    df_user = spark_proc.load_user_data(small_user_file)
    assert df_user.count() == 3
    
    df_hourly = spark_proc.aggregate_hourly(df_user, is_uci=False)
    assert df_hourly.count() == 2 # 00:00 and 01:00 hours
    
    # Sum for 00:00 should be 0.42 + 0.38 = 0.80
    first_hour = df_hourly.orderBy("timestamp").collect()[0]
    assert abs(first_hour["energy_kwh"] - 0.80) < 1e-6
