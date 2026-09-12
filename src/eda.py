import json
from pathlib import Path
from pyspark.sql import SparkSession, DataFrame, Window
import pyspark.sql.functions as F
from pyspark.sql.types import DoubleType

class EnergyDataAnalyzer:
    def __init__(self, spark: SparkSession):
        self.spark = spark
        
    def load_data(self, input_path: str | Path) -> DataFrame:
        """Loads cleaned parquet data safely."""
        path_str = str(input_path)
        if not path_str.endswith('.parquet') and Path(path_str + ".parquet").exists():
            path_str += ".parquet"
            
        try:
            return self.spark.read.parquet(path_str)
        except Exception as e:
            if "NANOS" in str(e):
                import pandas as pd
                pdf = pd.read_parquet(path_str)
                for col in pdf.columns:
                    if pd.api.types.is_datetime64_any_dtype(pdf[col]):
                        pdf[col] = pdf[col].astype('datetime64[us]')
                return self.spark.createDataFrame(pdf)
            raise e

    def calculate_dataset_statistics(self, df: DataFrame) -> dict:
        """Calculates overarching dataset statistics."""
        bounds = df.agg(
            F.min("timestamp").alias("min_ts"),
            F.max("timestamp").alias("max_ts"),
            F.count("*").alias("count")
        ).collect()[0]
        
        # Calculate numeric stats for energy_kwh
        stats = df.select(
            F.mean("energy_kwh").alias("mean"),
            F.stddev("energy_kwh").alias("stddev"),
            F.variance("energy_kwh").alias("variance"),
            F.min("energy_kwh").alias("min"),
            F.max("energy_kwh").alias("max")
        ).collect()[0]
        
        # Calculate percentiles
        percentiles = [0.25, 0.50, 0.75, 0.90, 0.95, 0.99]
        q_vals = df.approxQuantile("energy_kwh", percentiles, 0.01)
        
        start_date = bounds["min_ts"]
        end_date = bounds["max_ts"]
        duration_days = (end_date - start_date).total_seconds() / (24 * 3600) if start_date and end_date else 0
        
        return {
            "num_records": bounds["count"],
            "num_variables": len(df.columns),
            "start_date": str(start_date) if start_date else None,
            "end_date": str(end_date) if end_date else None,
            "total_duration_days": float(round(duration_days, 2)),
            "energy_kwh_stats": {
                "mean": float(stats["mean"]) if stats["mean"] else None,
                "median": float(q_vals[1]) if q_vals else None,
                "min": float(stats["min"]) if stats["min"] else None,
                "max": float(stats["max"]) if stats["max"] else None,
                "stddev": float(stats["stddev"]) if stats["stddev"] else None,
                "variance": float(stats["variance"]) if stats["variance"] else None,
                "percentile_25": float(q_vals[0]) if q_vals else None,
                "percentile_50": float(q_vals[1]) if q_vals else None,
                "percentile_75": float(q_vals[2]) if q_vals else None,
                "percentile_90": float(q_vals[3]) if q_vals else None,
                "percentile_95": float(q_vals[4]) if q_vals else None,
                "percentile_99": float(q_vals[5]) if q_vals else None,
            }
        }

    def enrich_with_temporal_features(self, df: DataFrame) -> DataFrame:
        """Generates temporary time features for EDA."""
        df = df.withColumn("date", F.date_trunc("day", F.col("timestamp")))
        df = df.withColumn("hour", F.hour("timestamp"))
        df = df.withColumn("month", F.month("timestamp"))
        
        # Spark dayofweek: 1=Sunday, 2=Monday, ..., 7=Saturday
        df = df.withColumn("dayofweek_num", F.dayofweek("timestamp"))
        df = df.withColumn("day_name", F.date_format("timestamp", "EEEE"))
        
        df = df.withColumn("is_weekend", F.when(F.col("dayofweek_num").isin([1, 7]), 1).otherwise(0))
        
        # Simple seasonal mapping (Northern Hemisphere standard)
        df = df.withColumn("season", 
            F.when(F.col("month").isin([12, 1, 2]), "Winter")
             .when(F.col("month").isin([3, 4, 5]), "Spring")
             .when(F.col("month").isin([6, 7, 8]), "Summer")
             .otherwise("Autumn")
        )
        return df

    def calculate_hourly_patterns(self, df: DataFrame) -> DataFrame:
        """Calculates average consumption by hour of day."""
        return df.groupBy("hour").agg(F.avg("energy_kwh").alias("avg_energy_kwh")).orderBy("hour")

    def calculate_daily_patterns(self, df: DataFrame) -> DataFrame:
        """Calculates daily consumption trends."""
        return df.groupBy("date").agg(
            F.sum("energy_kwh").alias("total_energy_kwh"),
            F.mean("energy_kwh").alias("mean_energy_kwh"),
            F.max("energy_kwh").alias("max_energy_kwh"),
            F.min("energy_kwh").alias("min_energy_kwh")
        ).orderBy("date")

    def calculate_weekly_patterns(self, df: DataFrame) -> DataFrame:
        """Calculates average consumption by day of week."""
        # Using dayofweek_num for sorting but returning name
        return df.groupBy("dayofweek_num", "day_name").agg(
            F.avg("energy_kwh").alias("avg_energy_kwh")
        ).orderBy("dayofweek_num")

    def calculate_monthly_patterns(self, df: DataFrame) -> DataFrame:
        """Calculates monthly consumption stats."""
        return df.groupBy("month").agg(
            F.sum("energy_kwh").alias("total_energy_kwh"),
            F.avg("energy_kwh").alias("avg_hourly_energy_kwh"),
            F.max("energy_kwh").alias("max_energy_kwh")
        ).orderBy("month")

    def calculate_seasonal_patterns(self, df: DataFrame) -> DataFrame:
        """Calculates seasonal consumption stats."""
        return df.groupBy("season").agg(
            F.avg("energy_kwh").alias("avg_energy_kwh")
        )

    def calculate_weekday_weekend_comparison(self, df: DataFrame) -> dict:
        """Compares weekday vs weekend consumption."""
        res = df.groupBy("is_weekend").agg(
            F.avg("energy_kwh").alias("mean"),
            F.expr("percentile_approx(energy_kwh, 0.5)").alias("median"),
            F.sum("energy_kwh").alias("total"),
            F.max("energy_kwh").alias("max")
        ).collect()
        
        comparison = {}
        for row in res:
            key = "weekend" if row["is_weekend"] == 1 else "weekday"
            comparison[key] = {
                "mean": float(row["mean"]) if row["mean"] else 0.0,
                "median": float(row["median"]) if row["median"] else 0.0,
                "total": float(row["total"]) if row["total"] else 0.0,
                "max": float(row["max"]) if row["max"] else 0.0
            }
        return comparison

    def analyze_peak_demand(self, df: DataFrame, p90: float, p95: float) -> DataFrame:
        """Identifies high-demand periods above thresholds."""
        return df.withColumn(
            "demand_level",
            F.when(F.col("energy_kwh") >= p95, "critical")
             .when(F.col("energy_kwh") >= p90, "high")
             .otherwise("normal")
        )

    def analyze_variability(self, df: DataFrame) -> dict:
        """Calculates CV and variability."""
        stats = df.select(
            F.mean("energy_kwh").alias("mean"),
            F.stddev("energy_kwh").alias("stddev")
        ).collect()[0]
        
        mean_val = stats["mean"]
        std_val = stats["stddev"]
        cv = (std_val / mean_val) if mean_val else None
        
        # Hourly variability (stddev by hour)
        hourly_var = df.groupBy("hour").agg(F.stddev("energy_kwh").alias("stddev_energy")).orderBy("hour").collect()
        hourly_std = {int(row["hour"]): float(row["stddev_energy"]) if row["stddev_energy"] else 0.0 for row in hourly_var}
        
        return {
            "overall_cv": float(cv) if cv else None,
            "overall_stddev": float(std_val) if std_val else None,
            "hourly_stddev": hourly_std
        }

    def analyze_submetering(self, df: DataFrame) -> dict:
        """Analyzes sub-metering contributions."""
        cols = df.columns
        if not all(c in cols for c in ["total_sub_metering_1", "total_sub_metering_2", "total_sub_metering_3"]):
            return {}
            
        totals = df.select(
            F.sum("total_sub_metering_1").alias("sm1"),
            F.sum("total_sub_metering_2").alias("sm2"),
            F.sum("total_sub_metering_3").alias("sm3")
        ).collect()[0]
        
        sm_total = (totals["sm1"] or 0) + (totals["sm2"] or 0) + (totals["sm3"] or 0)
        
        return {
            "sub_metering_1": {
                "total": float(totals["sm1"] or 0),
                "relative_contribution": float((totals["sm1"] or 0) / sm_total) if sm_total > 0 else 0
            },
            "sub_metering_2": {
                "total": float(totals["sm2"] or 0),
                "relative_contribution": float((totals["sm2"] or 0) / sm_total) if sm_total > 0 else 0
            },
            "sub_metering_3": {
                "total": float(totals["sm3"] or 0),
                "relative_contribution": float((totals["sm3"] or 0) / sm_total) if sm_total > 0 else 0
            }
        }

    def calculate_correlation_matrix(self, df: DataFrame) -> dict:
        """Calculates correlations between numeric variables in Spark."""
        numeric_cols = [c for c, t in df.dtypes if t in ('double', 'float', 'int', 'bigint')]
        if "energy_kwh" not in numeric_cols:
            return {}
            
        corr_matrix = {}
        # We only compute correlations with energy_kwh to save computation, 
        # or compute full matrix via Pandas for visualization.
        # Here we just compute energy_kwh vs others.
        for c in numeric_cols:
            if c != "energy_kwh":
                val = df.stat.corr("energy_kwh", c)
                corr_matrix[c] = float(val) if val else None
                
        return corr_matrix

    def calculate_autocorrelation(self, df: DataFrame) -> dict:
        """Calculates autocorrelation for specific lags."""
        lags = [1, 24, 48, 168]
        w = Window.orderBy("timestamp")
        
        df_lags = df.select("timestamp", "energy_kwh")
        for lag in lags:
            df_lags = df_lags.withColumn(f"lag_{lag}", F.lag("energy_kwh", lag).over(w))
            
        corrs = {}
        for lag in lags:
            # Only compute if we have more than 'lag' rows to avoid divide by zero on empty/small sets
            valid_rows = df_lags.filter(F.col(f"lag_{lag}").isNotNull()).count()
            if valid_rows > 1:
                try:
                    val = df_lags.stat.corr("energy_kwh", f"lag_{lag}")
                    corrs[f"lag_{lag}"] = float(val) if val else None
                except Exception:
                    corrs[f"lag_{lag}"] = None
            else:
                corrs[f"lag_{lag}"] = None
            
        return corrs
