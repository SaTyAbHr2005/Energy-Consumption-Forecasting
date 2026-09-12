import os
import json
from pathlib import Path
from typing import Dict, Any, Optional

from pyspark.sql import SparkSession, DataFrame
from pyspark.sql.types import StructType, StructField, StringType, DoubleType, TimestampType
import pyspark.sql.functions as F

class SparkProcessor:
    def __init__(self, app_name: str = "SmartGridEnergyProcessing"):
        """Initializes a local SparkSession."""
        self.spark = SparkSession.builder \
            .appName(app_name) \
            .master("local[*]") \
            .config("spark.sql.session.timeZone", "UTC") \
            .getOrCreate()
            
    def get_uci_schema(self) -> StructType:
        """Returns the explicit schema for the UCI dataset."""
        return StructType([
            StructField("Date", StringType(), True),
            StructField("Time", StringType(), True),
            StructField("Global_active_power", DoubleType(), True),
            StructField("Global_reactive_power", DoubleType(), True),
            StructField("Voltage", DoubleType(), True),
            StructField("Global_intensity", DoubleType(), True),
            StructField("Sub_metering_1", DoubleType(), True),
            StructField("Sub_metering_2", DoubleType(), True),
            StructField("Sub_metering_3", DoubleType(), True)
        ])

    def load_uci_data(self, file_path: str | Path) -> DataFrame:
        """Loads the UCI dataset using Spark with the explicit schema."""
        return self.spark.read.csv(
            str(file_path),
            sep=";",
            header=True,
            schema=self.get_uci_schema(),
            nullValue="?"  # Treat '?' as null
        )

    def load_user_data(self, file_path: str | Path) -> DataFrame:
        """Loads a pre-validated user CSV dataset."""
        schema = StructType([
            StructField("timestamp", StringType(), True),
            StructField("energy_consumption", DoubleType(), True)
        ])
        df = self.spark.read.csv(
            str(file_path),
            header=True,
            schema=schema
        )
        return df.withColumn("timestamp", F.to_timestamp("timestamp", "yyyy-MM-dd HH:mm:ss"))

    def process_uci_data(self, df: DataFrame) -> DataFrame:
        """
        Processes raw UCI data by constructing a timestamp and converting 
        Global_active_power to energy_kwh.
        """
        # Create timestamp from Date and Time
        # The UCI date format is d/M/yyyy and time is HH:mm:ss
        df_processed = df.withColumn(
            "timestamp", 
            F.to_timestamp(F.concat_ws(" ", F.col("Date"), F.col("Time")), "d/M/yyyy HH:mm:ss")
        )
        
        # Convert Global_active_power (kW per minute) to energy_kwh (kWh consumed in that minute)
        df_processed = df_processed.withColumn(
            "energy_kwh", 
            F.col("Global_active_power") / 60.0
        )
        
        return df_processed

    def calculate_missing_values(self, df: DataFrame, columns: list) -> dict:
        """Calculates missing values for specified columns using Spark."""
        exprs = [F.sum(F.col(c).isNull().cast("int")).alias(f"missing_{c}") for c in columns]
        result = df.agg(*exprs).collect()[0].asDict()
        return result

    def aggregate_hourly(self, df: DataFrame, is_uci: bool = True) -> DataFrame:
        """
        Aggregates data to an hourly resolution.
        Handles both UCI datasets and User datasets.
        """
        # Create an hour-truncated timestamp for grouping
        df_hourly = df.withColumn("hour", F.date_trunc("hour", F.col("timestamp")))
        
        if is_uci:
            return df_hourly.groupBy("hour").agg(
                F.sum("energy_kwh").alias("energy_kwh"),
                F.avg("Global_active_power").alias("avg_global_active_power"),
                F.avg("Global_reactive_power").alias("avg_global_reactive_power"),
                F.avg("Voltage").alias("avg_voltage"),
                F.avg("Global_intensity").alias("avg_global_intensity"),
                F.sum("Sub_metering_1").alias("total_sub_metering_1"),
                F.sum("Sub_metering_2").alias("total_sub_metering_2"),
                F.sum("Sub_metering_3").alias("total_sub_metering_3")
            ).withColumnRenamed("hour", "timestamp").orderBy("timestamp")
        else:
            return df_hourly.groupBy("hour").agg(
                F.sum("energy_consumption").alias("energy_kwh")
            ).withColumnRenamed("hour", "timestamp").orderBy("timestamp")

    def aggregate_15min(self, df: DataFrame, is_uci: bool = True) -> DataFrame:
        """
        Aggregates data to 15-minute resolution using Spark time windows.
        """
        if is_uci:
            return df.groupBy(F.window(F.col("timestamp"), "15 minutes")).agg(
                F.sum("energy_kwh").alias("energy_kwh"),
                F.avg("Global_active_power").alias("avg_global_active_power"),
                F.avg("Global_reactive_power").alias("avg_global_reactive_power"),
                F.avg("Voltage").alias("avg_voltage"),
                F.avg("Global_intensity").alias("avg_global_intensity"),
                F.sum("Sub_metering_1").alias("total_sub_metering_1"),
                F.sum("Sub_metering_2").alias("total_sub_metering_2"),
                F.sum("Sub_metering_3").alias("total_sub_metering_3")
            ).select(F.col("window.start").alias("timestamp"), "*").drop("window").orderBy("timestamp")
        else:
            return df.groupBy(F.window(F.col("timestamp"), "15 minutes")).agg(
                F.sum("energy_consumption").alias("energy_kwh")
            ).select(F.col("window.start").alias("timestamp"), "*").drop("window").orderBy("timestamp")

    def write_parquet(self, df: DataFrame, output_path: str | Path):
        """Writes the DataFrame to Parquet format."""
        try:
            df.write.mode("overwrite").parquet(str(output_path))
        except Exception as e:
            error_str = str(e).lower()
            if "hadoop" in error_str or "winutils" in error_str:
                print("\n[WARNING] Spark Parquet write failed due to missing Hadoop native libraries (winutils.exe) on Windows.")
                print("[WARNING] Falling back to pandas to write the aggregated dataset to Parquet.")
                # Since df is already aggregated, it's safe to collect to Pandas
                df.toPandas().to_parquet(str(output_path) + ".parquet", index=False, engine='pyarrow', coerce_timestamps='us', allow_truncated_timestamps=True)
            else:
                raise e
        
    def stop(self):
        """Stops the SparkSession."""
        self.spark.stop()
