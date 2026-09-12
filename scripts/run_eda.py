import sys
import os
import json
from pathlib import Path
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from pyspark.sql import SparkSession
import pyspark.sql.functions as F

# Ensure driver and worker use the exact same Python executable
os.environ["PYSPARK_PYTHON"] = sys.executable
os.environ["PYSPARK_DRIVER_PYTHON"] = sys.executable

# Add the project root to Python path
sys.path.append(str(Path(__file__).parent.parent))

from src.eda import EnergyDataAnalyzer

def save_csv(pdf: pd.DataFrame, path: Path):
    """Helper to save Pandas DataFrame to CSV."""
    path.parent.mkdir(parents=True, exist_ok=True)
    pdf.to_csv(path, index=False)

def plot_histogram(data: pd.Series, path: Path, title: str, xlabel: str):
    """Helper to plot and save a histogram."""
    plt.figure(figsize=(10, 6))
    sns.histplot(data.dropna(), bins=50, kde=True, color='skyblue')
    plt.title(title)
    plt.xlabel(xlabel)
    plt.ylabel('Frequency')
    plt.grid(axis='y', alpha=0.75)
    plt.tight_layout()
    plt.savefig(path)
    plt.close()

def plot_boxplot(data: pd.Series, path: Path, title: str):
    """Helper to plot and save a boxplot."""
    plt.figure(figsize=(10, 6))
    sns.boxplot(x=data.dropna(), color='lightgreen')
    plt.title(title)
    plt.xlabel('Energy Consumption (kWh)')
    plt.tight_layout()
    plt.savefig(path)
    plt.close()

def plot_line(x: pd.Series, y: pd.Series, path: Path, title: str, xlabel: str, ylabel: str):
    """Helper to plot a simple line graph."""
    plt.figure(figsize=(12, 6))
    plt.plot(x, y, marker='o', linestyle='-', color='b')
    plt.title(title)
    plt.xlabel(xlabel)
    plt.ylabel(ylabel)
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(path)
    plt.close()

def plot_bar(x: pd.Series, y: pd.Series, path: Path, title: str, xlabel: str, ylabel: str):
    """Helper to plot a simple bar graph."""
    plt.figure(figsize=(10, 6))
    sns.barplot(x=x, y=y, palette='viridis')
    plt.title(title)
    plt.xlabel(xlabel)
    plt.ylabel(ylabel)
    if len(x) > 7:
        plt.xticks(rotation=45)
    plt.grid(axis='y', alpha=0.75)
    plt.tight_layout()
    plt.savefig(path)
    plt.close()

def plot_heatmap(df: pd.DataFrame, path: Path, title: str):
    """Helper to plot heatmap."""
    plt.figure(figsize=(14, 6))
    sns.heatmap(df, cmap="YlGnBu", annot=False)
    plt.title(title)
    plt.xlabel("Hour of Day")
    plt.ylabel("Day of Week")
    plt.tight_layout()
    plt.savefig(path)
    plt.close()

def main():
    print("=" * 60)
    print("Exploratory Data Analysis and Energy Analytics")
    print("=" * 60)
    
    project_root = Path(__file__).parent.parent
    input_path = project_root / "data" / "processed" / "uci_hourly_clean"
    
    analytics_dir = project_root / "results" / "analytics"
    figures_dir = project_root / "results" / "figures"
    metrics_dir = project_root / "results" / "metrics"
    
    for d in [analytics_dir, figures_dir, metrics_dir]:
        d.mkdir(parents=True, exist_ok=True)
        
    print("Initializing SparkSession (local)...")
    spark = SparkSession.builder \
        .appName("EnergyEDA") \
        .master("local[*]") \
        .config("spark.sql.session.timeZone", "UTC") \
        .getOrCreate()
        
    try:
        analyzer = EnergyDataAnalyzer(spark)
        
        print("Loading dataset...")
        df = analyzer.load_data(input_path)
        
        # 1. Overall Statistics
        print("Calculating overarching statistics...")
        stats = analyzer.calculate_dataset_statistics(df)
        
        # 2. Enrich with temporal features for EDA
        print("Generating temporal features for EDA...")
        df_enriched = analyzer.enrich_with_temporal_features(df)
        
        # Collect base Pandas DF for quick plotting of distributions and heatmaps
        # We only take the columns needed for plotting to keep it lightweight
        pdf = df_enriched.select("timestamp", "energy_kwh", "hour", "day_name", "date").toPandas()
        
        print("Generating Distribution Plots...")
        plot_histogram(pdf["energy_kwh"], figures_dir / "energy_distribution.png", 
                       "Distribution of Hourly Energy Consumption", "Energy (kWh)")
        plot_boxplot(pdf["energy_kwh"], figures_dir / "energy_boxplot.png", 
                     "Boxplot of Hourly Energy Consumption (Outliers Preserved)")
        
        # 3. Hourly Patterns
        print("Calculating Hourly Patterns...")
        hourly_df = analyzer.calculate_hourly_patterns(df_enriched)
        hourly_pdf = hourly_df.toPandas()
        save_csv(hourly_pdf, analytics_dir / "hourly_profile.csv")
        plot_line(hourly_pdf["hour"], hourly_pdf["avg_energy_kwh"], figures_dir / "hourly_consumption_pattern.png", 
                  "Average Energy Consumption by Hour of Day", "Hour", "Avg Energy (kWh)")
        
        highest_hour = int(hourly_pdf.loc[hourly_pdf["avg_energy_kwh"].idxmax()]["hour"])
        lowest_hour = int(hourly_pdf.loc[hourly_pdf["avg_energy_kwh"].idxmin()]["hour"])
        
        # 4. Peak Demand Analysis
        print("Calculating Peak Demand Analysis...")
        p90 = stats["energy_kwh_stats"]["percentile_90"]
        p95 = stats["energy_kwh_stats"]["percentile_95"]
        
        df_demand = analyzer.analyze_peak_demand(df_enriched, p90, p95)
        demand_counts = df_demand.groupBy("demand_level").count().collect()
        demand_summary = {row["demand_level"]: row["count"] for row in demand_counts}
        
        # Plot peaks over time
        plt.figure(figsize=(14, 6))
        plt.plot(pdf["timestamp"], pdf["energy_kwh"], alpha=0.5, label="Energy (kWh)")
        plt.axhline(p90, color='orange', linestyle='--', label=f"90th PCTL ({p90:.2f})")
        plt.axhline(p95, color='red', linestyle='--', label=f"95th PCTL ({p95:.2f})")
        plt.title("Energy Consumption with Peak Demand Thresholds")
        plt.xlabel("Time")
        plt.ylabel("Energy (kWh)")
        plt.legend()
        plt.tight_layout()
        plt.savefig(figures_dir / "peak_demand_analysis.png")
        plt.close()
        
        # Peak by hour
        high_demand_pdf = df_demand.filter(F.col("demand_level") != "normal").select("hour", "day_name").toPandas()
        if not high_demand_pdf.empty:
            peak_by_hour = high_demand_pdf["hour"].value_counts().sort_index()
            plot_bar(peak_by_hour.index, peak_by_hour.values, figures_dir / "peak_by_hour.png",
                     "Number of High Demand Events by Hour", "Hour", "Count")
            
            peak_by_day = high_demand_pdf["day_name"].value_counts()
            plot_bar(peak_by_day.index, peak_by_day.values, figures_dir / "peak_by_weekday.png",
                     "Number of High Demand Events by Day", "Day of Week", "Count")
        
        # 5. Daily Analysis
        print("Calculating Daily Patterns...")
        daily_df = analyzer.calculate_daily_patterns(df_enriched)
        daily_pdf = daily_df.toPandas()
        save_csv(daily_pdf, analytics_dir / "daily_consumption.csv")
        
        # Plot daily
        plt.figure(figsize=(14, 6))
        plt.plot(daily_pdf["date"], daily_pdf["total_energy_kwh"], color='green')
        plt.title("Daily Energy Consumption Trend")
        plt.xlabel("Date")
        plt.ylabel("Total Energy (kWh)")
        plt.grid(True)
        plt.tight_layout()
        plt.savefig(figures_dir / "daily_consumption_trend.png")
        plt.close()
        
        # 6. Weekly / Weekday Analysis
        print("Calculating Weekly Patterns...")
        weekly_df = analyzer.calculate_weekly_patterns(df_enriched)
        weekly_pdf = weekly_df.toPandas()
        save_csv(weekly_pdf, analytics_dir / "weekday_profile.csv")
        plot_bar(weekly_pdf["day_name"], weekly_pdf["avg_energy_kwh"], figures_dir / "weekday_consumption.png",
                 "Average Energy Consumption by Day of Week", "Day of Week", "Avg Energy (kWh)")
        
        highest_day = weekly_pdf.loc[weekly_pdf["avg_energy_kwh"].idxmax()]["day_name"]
        lowest_day = weekly_pdf.loc[weekly_pdf["avg_energy_kwh"].idxmin()]["day_name"]
        
        print("Calculating Weekday vs Weekend...")
        weekend_comparison = analyzer.calculate_weekday_weekend_comparison(df_enriched)
        
        plt.figure(figsize=(8, 6))
        sns.barplot(x=list(weekend_comparison.keys()), y=[v["mean"] for v in weekend_comparison.values()])
        plt.title("Average Consumption: Weekday vs Weekend")
        plt.ylabel("Average Energy (kWh)")
        plt.tight_layout()
        plt.savefig(figures_dir / "weekday_vs_weekend.png")
        plt.close()
        
        # 7. Heatmap
        print("Generating Heatmap...")
        heatmap_data = pdf.pivot_table(values="energy_kwh", index="day_name", columns="hour", aggfunc="mean")
        # Ensure correct day ordering
        days_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        heatmap_data = heatmap_data.reindex(days_order)
        plot_heatmap(heatmap_data, figures_dir / "hour_day_heatmap.png", "Average Energy Consumption Heatmap")
        
        # 8. Monthly and Seasonal
        print("Calculating Monthly & Seasonal Patterns...")
        monthly_df = analyzer.calculate_monthly_patterns(df_enriched)
        monthly_pdf = monthly_df.toPandas()
        save_csv(monthly_pdf, analytics_dir / "monthly_consumption.csv")
        plot_bar(monthly_pdf["month"], monthly_pdf["total_energy_kwh"], figures_dir / "monthly_consumption.png",
                 "Total Energy Consumption by Month", "Month", "Total Energy (kWh)")
        
        seasonal_df = analyzer.calculate_seasonal_patterns(df_enriched)
        seasonal_pdf = seasonal_df.toPandas()
        plot_bar(seasonal_pdf["season"], seasonal_pdf["avg_energy_kwh"], figures_dir / "seasonal_consumption.png",
                 "Average Energy Consumption by Season", "Season", "Avg Energy (kWh)")
        
        # 9. Rolling Statistics
        print("Calculating Rolling Statistics...")
        # Since df is large, use Pandas daily aggregation for rolling trend
        daily_pdf.set_index("date", inplace=True)
        daily_pdf["rolling_7d"] = daily_pdf["total_energy_kwh"].rolling(window=7).mean()
        
        plt.figure(figsize=(14, 6))
        plt.plot(daily_pdf.index, daily_pdf["total_energy_kwh"], label="Daily Total", alpha=0.4)
        plt.plot(daily_pdf.index, daily_pdf["rolling_7d"], label="7-Day Rolling Mean", color='red')
        plt.title("Long Term Trend with 7-Day Rolling Mean")
        plt.xlabel("Date")
        plt.ylabel("Energy (kWh)")
        plt.legend()
        plt.grid(True)
        plt.tight_layout()
        plt.savefig(figures_dir / "rolling_consumption.png")
        plt.close()
        
        # 10. Long Term Consumption Trend (Monthly Average)
        # We can use the actual timestamp mapped to Year-Month for long-term trend
        pdf['year_month'] = pdf['timestamp'].dt.to_period('M')
        monthly_trend = pdf.groupby('year_month')['energy_kwh'].sum().reset_index()
        monthly_trend['year_month'] = monthly_trend['year_month'].astype(str)
        plt.figure(figsize=(14, 6))
        plt.plot(monthly_trend['year_month'], monthly_trend['energy_kwh'], marker='o')
        plt.xticks(rotation=45)
        plt.title("Long-Term Monthly Total Consumption")
        plt.xlabel("Month")
        plt.ylabel("Total Energy (kWh)")
        plt.grid(True)
        plt.tight_layout()
        plt.savefig(figures_dir / "long_term_consumption.png")
        plt.close()
        
        # 11. Sub-metering Analysis
        print("Analyzing Sub-metering...")
        submetering = analyzer.analyze_submetering(df_enriched)
        if submetering:
            labels = list(submetering.keys())
            sizes = [v["total"] for v in submetering.values()]
            
            plt.figure(figsize=(8, 8))
            plt.pie(sizes, labels=labels, autopct='%1.1f%%', startangle=140, colors=['#ff9999','#66b3ff','#99ff99'])
            plt.title("Total Sub-metering Contribution")
            plt.tight_layout()
            plt.savefig(figures_dir / "submetering_consumption.png")
            plt.close()
            
            with open(analytics_dir / "submetering_profile.json", "w") as f:
                json.dump(submetering, f, indent=4)
        
        # 12. Correlation Analysis
        print("Calculating Correlation Matrix...")
        numeric_cols = [c for c, t in df_enriched.dtypes if t in ('double', 'float', 'int', 'bigint')]
        if numeric_cols:
            full_pdf = df_enriched.select(numeric_cols).toPandas()
            corr_matrix = full_pdf.corr()
            plt.figure(figsize=(10, 8))
            sns.heatmap(corr_matrix, annot=True, cmap='coolwarm', fmt=".2f", vmin=-1, vmax=1)
            plt.title("Correlation Matrix of Numeric Features")
            plt.tight_layout()
            plt.savefig(figures_dir / "correlation_matrix.png")
            plt.close()
            
            target_corr = analyzer.calculate_correlation_matrix(df_enriched)
        else:
            target_corr = {}
            
        # 13. Variability
        print("Analyzing Variability...")
        variability = analyzer.analyze_variability(df_enriched)
        
        # 14. Autocorrelation
        print("Calculating Autocorrelation...")
        autocorr = analyzer.calculate_autocorrelation(df_enriched)
        
        if autocorr:
            plt.figure(figsize=(8, 6))
            sns.barplot(x=list(autocorr.keys()), y=list(autocorr.values()))
            plt.title("Autocorrelation of Energy Consumption at Key Lags")
            plt.xlabel("Lag (Hours)")
            plt.ylabel("Autocorrelation Coefficient")
            plt.tight_layout()
            plt.savefig(figures_dir / "autocorrelation.png")
            plt.close()

        # Build JSON Summary
        highest_month_row = monthly_pdf.loc[monthly_pdf["total_energy_kwh"].idxmax()]
        lowest_month_row = monthly_pdf.loc[monthly_pdf["total_energy_kwh"].idxmin()]
        
        eda_summary = {
            "dataset_overview": {
                "num_records": stats["num_records"],
                "num_variables": stats["num_variables"],
                "start_date": stats["start_date"],
                "end_date": stats["end_date"],
                "total_duration_days": stats["total_duration_days"]
            },
            "consumption_statistics": stats["energy_kwh_stats"],
            "hourly_analysis": {
                "highest_average_consumption_hour": highest_hour,
                "lowest_average_consumption_hour": lowest_hour,
                "max_hourly_average": float(hourly_pdf["avg_energy_kwh"].max()),
                "min_hourly_average": float(hourly_pdf["avg_energy_kwh"].min())
            },
            "weekday_weekend_analysis": {
                "highest_consumption_weekday": highest_day,
                "lowest_consumption_weekday": lowest_day,
                "weekday_average_kwh": weekend_comparison.get("weekday", {}).get("mean"),
                "weekend_average_kwh": weekend_comparison.get("weekend", {}).get("mean")
            },
            "monthly_analysis": {
                "highest_consumption_month": int(highest_month_row["month"]),
                "lowest_consumption_month": int(lowest_month_row["month"])
            },
            "peak_demand_analysis": {
                "percentile_90_threshold": p90,
                "percentile_95_threshold": p95,
                "maximum_observed_demand": stats["energy_kwh_stats"]["max"],
                "high_demand_hours_count": demand_summary.get("high", 0),
                "critical_demand_hours_count": demand_summary.get("critical", 0)
            },
            "submetering_analysis": submetering,
            "variability_analysis": {
                "overall_cv": variability["overall_cv"],
                "overall_stddev": variability["overall_stddev"]
            },
            "correlation_analysis": target_corr,
            "autocorrelation_analysis": autocorr
        }
        
        with open(metrics_dir / "eda_summary.json", "w") as f:
            json.dump(eda_summary, f, indent=4)
            
        print("\nEDA completed successfully.")
        print(f"Results saved to {metrics_dir / 'eda_summary.json'}")
        
    except Exception as e:
        print(f"\nError during EDA: {str(e)}")
        import traceback
        traceback.print_exc()
    finally:
        print("\nStopping SparkSession...")
        spark.stop()
        print("Done.")

if __name__ == "__main__":
    main()
