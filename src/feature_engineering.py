import math
from pyspark.sql import DataFrame, Window
import pyspark.sql.functions as F

class FeatureEngineer:
    def __init__(self, spark):
        self.spark = spark

    def create_calendar_features(self, df: DataFrame, timestamp_col: str = "timestamp") -> DataFrame:
        """Creates standard calendar/time features."""
        df = df.withColumn("year", F.year(timestamp_col))
        df = df.withColumn("month", F.month(timestamp_col))
        df = df.withColumn("day", F.dayofmonth(timestamp_col))
        df = df.withColumn("day_of_month", F.dayofmonth(timestamp_col))
        # Spark dayofweek: 1=Sunday, 2=Monday, ..., 7=Saturday
        # We adjust to 0=Monday ... 6=Sunday
        df = df.withColumn("day_of_week", (F.dayofweek(timestamp_col) + 5) % 7)
        df = df.withColumn("hour", F.hour(timestamp_col))
        df = df.withColumn("week_of_year", F.weekofyear(timestamp_col))
        df = df.withColumn("quarter", F.quarter(timestamp_col))
        
        # is_weekend: Saturday (5) or Sunday (6)
        df = df.withColumn("is_weekend", F.when(F.col("day_of_week").isin([5, 6]), 1).otherwise(0))
        
        return df

    def create_cyclical_features(self, df: DataFrame) -> DataFrame:
        """Encodes hour, day_of_week, and month cyclically to preserve circular distance."""
        # Hour (0-23)
        df = df.withColumn("hour_sin", F.sin(2 * math.pi * F.col("hour") / 24))
        df = df.withColumn("hour_cos", F.cos(2 * math.pi * F.col("hour") / 24))
        
        # Day of week (0-6)
        df = df.withColumn("dow_sin", F.sin(2 * math.pi * F.col("day_of_week") / 7))
        df = df.withColumn("dow_cos", F.cos(2 * math.pi * F.col("day_of_week") / 7))
        
        # Month (1-12)
        df = df.withColumn("month_sin", F.sin(2 * math.pi * F.col("month") / 12))
        df = df.withColumn("month_cos", F.cos(2 * math.pi * F.col("month") / 12))
        
        return df

    def create_lag_features(self, df: DataFrame, target_col: str = "energy_kwh", lags: list = [1, 3, 6, 12, 24, 48, 72, 168], order_col: str = "timestamp") -> DataFrame:
        """Creates autoregressive lag features securely ordered by time."""
        w = Window.orderBy(order_col)
        for lag in lags:
            df = df.withColumn(f"lag_{lag}", F.lag(target_col, lag).over(w))
        return df

    def create_rolling_features(self, df: DataFrame, target_col: str = "energy_kwh", windows: list = [3, 6, 12, 24, 168], order_col: str = "timestamp") -> DataFrame:
        """Creates rolling statistics. STRICTLY EXCLUDES current observation to prevent data leakage."""
        for w_size in windows:
            # rowsBetween(-N, -1) prevents target leakage by only including up to the previous row
            w = Window.orderBy(order_col).rowsBetween(-w_size, -1)
            df = df.withColumn(f"rolling_mean_{w_size}", F.mean(target_col).over(w))
            
            # Additional stats for 24h rolling
            if w_size == 24:
                df = df.withColumn(f"rolling_std_{w_size}", F.stddev(target_col).over(w))
                df = df.withColumn(f"rolling_min_{w_size}", F.min(target_col).over(w))
                df = df.withColumn(f"rolling_max_{w_size}", F.max(target_col).over(w))
                
        return df

    def create_trend_features(self, df: DataFrame) -> DataFrame:
        """Creates short-term and daily trend indicators from existing lags."""
        # Represents recent trajectory (e.g., is consumption going up or down right now)
        df = df.withColumn("trend_3h", F.col("lag_1") - F.col("lag_3"))
        df = df.withColumn("trend_24h", F.col("lag_1") - F.col("lag_24"))
        return df

    def create_contextual_features(self, df: DataFrame, p90_threshold: float) -> DataFrame:
        """Creates context signals (like whether previous hour was a peak)."""
        df = df.withColumn(
            "is_high_demand_previous_hour", 
            F.when(F.col("lag_1") >= p90_threshold, 1).otherwise(0)
        )
        return df

    def drop_insufficient_history(self, df: DataFrame, max_lag: int = 168) -> DataFrame:
        """Removes the initial burn-in period and any rows with nulls from long missing data gaps."""
        # Drop rows where lag_168 is null
        df = df.filter(F.col(f"lag_{max_lag}").isNotNull())
        # Drop any remaining rows with nulls in features or target
        df = df.dropna()
        return df
