import json
from pathlib import Path
from pyspark.sql import SparkSession, DataFrame
import pyspark.sql.functions as F
from pyspark.sql.window import Window

class DataPreprocessor:
    def __init__(self, spark: SparkSession):
        self.spark = spark
        self.report = {
            "preprocessing_status": "started"
        }

    def load_data(self, input_path: str | Path) -> DataFrame:
        """Loads processed parquet data."""
        path_str = str(input_path)
        if not path_str.endswith('.parquet') and Path(path_str + ".parquet").exists():
            path_str += ".parquet"
            
        try:
            return self.spark.read.parquet(path_str)
        except Exception as e:
            if "NANOS" in str(e):
                import pandas as pd
                print("\n[WARNING] Detected NANOS timestamps in Parquet. Loading via Pandas...")
                pdf = pd.read_parquet(path_str)
                # Convert datetime nanoseconds to microseconds
                for col in pdf.columns:
                    if pd.api.types.is_datetime64_any_dtype(pdf[col]):
                        pdf[col] = pdf[col].astype('datetime64[us]')
                return self.spark.createDataFrame(pdf)
            raise e
        
    def standardize_user_data(self, df: DataFrame) -> DataFrame:
        """Standardizes user schema to internal schema."""
        if "energy_consumption" in df.columns:
            df = df.withColumnRenamed("energy_consumption", "energy_kwh")
        return df

    def validate_timestamps(self, df: DataFrame) -> DataFrame:
        """Checks min, max, null timestamps."""
        count_before = df.count()
        df = df.filter(F.col("timestamp").isNotNull())
        count_after = df.count()
        null_ts = count_before - count_after
        
        bounds = df.select(
            F.min("timestamp").alias("min_ts"), 
            F.max("timestamp").alias("max_ts")
        ).collect()[0]
        
        self.report["null_timestamps_removed"] = null_ts
        self.report["start_timestamp"] = str(bounds["min_ts"]) if bounds["min_ts"] else None
        self.report["end_timestamp"] = str(bounds["max_ts"]) if bounds["max_ts"] else None
        
        return df

    def handle_duplicates(self, df: DataFrame) -> DataFrame:
        """Detects and aggregates duplicate timestamps."""
        self.report["records_before_dedup"] = df.count()
        
        # Find duplicates
        ts_counts = df.groupBy("timestamp").count()
        duplicates = ts_counts.filter(F.col("count") > 1).count()
        self.report["duplicate_timestamps"] = duplicates
        
        if duplicates > 0:
            # Aggregate duplicates: sum for total sub-meterings, average for the rest
            agg_exprs = []
            for col_name in df.columns:
                if col_name == "timestamp":
                    continue
                if col_name.startswith("total_") or col_name == "energy_kwh":
                    agg_exprs.append(F.sum(col_name).alias(col_name))
                else:
                    agg_exprs.append(F.avg(col_name).alias(col_name))
            
            df = df.groupBy("timestamp").agg(*agg_exprs)
            
        self.report["records_after_dedup"] = df.count()
        return df

    def create_continuous_timeseries(self, df: DataFrame) -> DataFrame:
        """Fills missing hours with null rows to create a continuous time series."""
        bounds = df.select(F.min("timestamp").alias("min"), F.max("timestamp").alias("max")).collect()[0]
        min_ts = bounds["min"]
        max_ts = bounds["max"]
        
        if not min_ts or not max_ts:
            return df
            
        # Create continuous hourly sequence using Spark SQL
        seq_df = self.spark.sql(f"""
            SELECT sequence(
                to_timestamp('{min_ts}'), 
                to_timestamp('{max_ts}'), 
                interval 1 hour
            ) as ts_array
        """)
        seq_df = seq_df.withColumn("timestamp", F.explode("ts_array")).select("timestamp")
        
        self.report["expected_hourly_records"] = seq_df.count()
        
        # Left outer join with original data to insert missing timestamps
        continuous_df = seq_df.join(df, on="timestamp", how="left")
        
        self.report["actual_hourly_records"] = self.report["records_after_dedup"]
        self.report["missing_hourly_records"] = self.report["expected_hourly_records"] - self.report["actual_hourly_records"]
        
        return continuous_df.orderBy("timestamp")

    def handle_missing_values(self, df: DataFrame) -> DataFrame:
        """Handles missing values with time-based interpolation for short gaps."""
        # Calculate missing values before
        missing_before = {}
        numeric_cols = [c for c, t in df.dtypes if t in ('double', 'float', 'int', 'bigint')]
        for c in numeric_cols:
            missing_before[c] = df.filter(F.col(c).isNull()).count()
        self.report["missing_values_before"] = missing_before
        
        # Target column logic
        if "energy_kwh" in df.columns:
            # Detect gaps
            df = df.withColumn("is_missing", F.when(F.col("energy_kwh").isNull(), 1).otherwise(0))
            w_ff = Window.orderBy("timestamp")
            
            # Create a group for consecutive nulls
            df = df.withColumn("gap_group", F.sum(F.when(F.col("is_missing") == 0, 1).otherwise(0)).over(w_ff))
            w_gap = Window.partitionBy("gap_group")
            df = df.withColumn("gap_size", F.when(F.col("is_missing") == 1, F.sum("is_missing").over(w_gap)).otherwise(0))
            
            # Forward fill and backward fill
            df = df.withColumn("ffill_energy", F.last("energy_kwh", ignorenulls=True).over(w_ff))
            w_bf = Window.orderBy("timestamp").rowsBetween(0, Window.unboundedFollowing)
            df = df.withColumn("bfill_energy", F.first("energy_kwh", ignorenulls=True).over(w_bf))
            
            # Simple average for interpolation
            df = df.withColumn("interpolated_energy", (F.col("ffill_energy") + F.col("bfill_energy")) / 2.0)
            
            # Fill small gaps (<= 3 hours)
            df = df.withColumn("energy_kwh", 
                F.when((F.col("is_missing") == 1) & (F.col("gap_size") <= 3), F.col("interpolated_energy"))
                 .otherwise(F.col("energy_kwh"))
            )
            
            # Flag long gaps (gap_size > 3)
            df = df.withColumn("is_long_gap", F.when(F.col("gap_size") > 3, 1).otherwise(0))
            
            # Clean up temporary columns
            df = df.drop("is_missing", "gap_group", "gap_size", "ffill_energy", "bfill_energy", "interpolated_energy")
            
        # Calculate missing values after
        missing_after = {}
        for c in numeric_cols:
            missing_after[c] = df.filter(F.col(c).isNull()).count()
        self.report["missing_values_after"] = missing_after
        
        return df

    def detect_outliers(self, df: DataFrame) -> DataFrame:
        """Detects outliers using IQR on energy_kwh."""
        if "energy_kwh" not in df.columns:
            return df
            
        try:
            quantiles = df.approxQuantile("energy_kwh", [0.25, 0.75], 0.01)
            if quantiles and len(quantiles) == 2:
                q1, q3 = quantiles[0], quantiles[1]
                iqr = q3 - q1
                lower_bound = q1 - 1.5 * iqr
                upper_bound = q3 + 1.5 * iqr
                
                df = df.withColumn("is_energy_outlier", 
                    F.when(F.col("energy_kwh") > upper_bound, 1)
                     .when(F.col("energy_kwh") < lower_bound, 1)
                     .otherwise(0)
                )
                
                outliers = df.filter(F.col("is_energy_outlier") == 1).count()
                self.report["outlier_count"] = outliers
                self.report["outlier_lower_bound"] = lower_bound
                self.report["outlier_upper_bound"] = upper_bound
            else:
                df = df.withColumn("is_energy_outlier", F.lit(0))
                self.report["outlier_count"] = 0
        except Exception:
            df = df.withColumn("is_energy_outlier", F.lit(0))
            self.report["outlier_count"] = 0
            
        return df
        
    def write_parquet(self, df: DataFrame, output_path: str | Path):
        """Writes the DataFrame to Parquet format safely on Windows."""
        try:
            df.write.mode("overwrite").parquet(str(output_path))
        except Exception as e:
            error_str = str(e).lower()
            if "hadoop" in error_str or "winutils" in error_str:
                print("[WARNING] Spark Parquet write failed due to missing Hadoop native libraries.")
                print("[WARNING] Falling back to pandas to write to Parquet.")
                # Safe to collect because it's only hourly data (max ~35k rows)
                df.toPandas().to_parquet(str(output_path) + ".parquet", index=False, engine='pyarrow', coerce_timestamps='us', allow_truncated_timestamps=True)
            else:
                raise e

    def process(self, input_path: str | Path, output_path: str | Path) -> DataFrame:
        """Runs the full preprocessing pipeline."""
        df = self.load_data(input_path)
        self.report["input_records"] = df.count()
        
        df = self.standardize_user_data(df)
        df = self.validate_timestamps(df)
        df = self.handle_duplicates(df)
        df = self.create_continuous_timeseries(df)
        df = self.handle_missing_values(df)
        df = self.detect_outliers(df)
        
        # Enforce non-negative energy if it exists
        if "energy_kwh" in df.columns:
            negative_count = df.filter(F.col("energy_kwh") < 0).count()
            self.report["negative_energy_values"] = negative_count
            if negative_count > 0:
                # Floor at 0
                df = df.withColumn("energy_kwh", F.when(F.col("energy_kwh") < 0, 0.0).otherwise(F.col("energy_kwh")))
                
        self.report["output_records"] = df.count()
        self.report["preprocessing_status"] = "success"
        
        self.write_parquet(df, output_path)
        return df
