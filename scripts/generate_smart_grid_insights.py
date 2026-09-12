"""Generate Module 9 forecast-based smart-grid decision-support artifacts."""
from pathlib import Path
import json
import sys

import matplotlib.pyplot as plt
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.smart_grid_insights import (  # noqa: E402
    TOUConfig, build_peak_demand_forecast, calculate_tou_cost, daily_savings_analysis,
    energy_insights, generate_recommendations, json_dump, recommend_load_shifts, tou_rate,
    tou_summary,
)


ROOT = Path(__file__).resolve().parents[1]
METRICS = ROOT / "results" / "metrics"
FIGURES = ROOT / "results" / "figures" / "smart_grid"


def _load_predictions() -> pd.DataFrame:
    path = ROOT / "results" / "predictions" / "xgboost_predictions.parquet"
    data = pd.read_parquet(path)
    # The optimized artifact contains both horizons; use the selected 1-hour
    # model output as the consistent hourly forecast schedule.
    if "horizon" in data:
        data = data[data["horizon"] == 1]
    return data.rename(columns={"predicted": "predicted"})


def _save_figures(forecast, costs, shifts, daily, threshold, config):
    FIGURES.mkdir(parents=True, exist_ok=True)
    plt.figure(figsize=(12, 4))
    plt.plot(forecast["timestamp"], forecast["predicted_consumption"], label="Forecast")
    plt.axhline(threshold, color="red", linestyle="--", label="High-demand threshold")
    plt.scatter(forecast.loc[forecast["is_peak"], "timestamp"],
                forecast.loc[forecast["is_peak"], "predicted_consumption"], color="red", s=12)
    plt.legend(); plt.ylabel("kWh"); plt.title("Forecasted Demand and Peak Threshold")
    plt.tight_layout(); plt.savefig(FIGURES / "forecast_peak_demand.png"); plt.close()

    hours = list(range(24))
    plt.figure(figsize=(10, 4))
    plt.step(hours, [tou_rate(h, config) for h in hours], where="mid")
    plt.xticks(hours); plt.ylabel("Illustrative INR/kWh"); plt.xlabel("Hour")
    plt.title("Illustrative TOU Pricing Simulation")
    plt.tight_layout(); plt.savefig(FIGURES / "tou_pricing_simulation.png"); plt.close()

    plt.figure(figsize=(6, 4))
    baseline = float(costs["simulated_cost_inr"].sum())
    optimized = float(daily["optimized_simulated_cost"].sum()) if not daily.empty else baseline
    plt.bar(["Baseline simulated", "Potential optimized"], [baseline, optimized])
    plt.ylabel("INR"); plt.title("Baseline vs Optimized Simulated Cost")
    plt.tight_layout(); plt.savefig(FIGURES / "cost_savings_comparison.png"); plt.close()

    plt.figure(figsize=(10, 4))
    if shifts.empty:
        plt.text(0.5, 0.5, "No positive-savings shifts identified", ha="center", va="center")
        plt.axis("off")
    else:
        for _, row in shifts.iterrows():
            plt.plot([row["source_timestamp"], row["destination_timestamp"]],
                     [row["source_predicted_kwh"], row["destination_predicted_kwh"]], "o-", alpha=.7)
        plt.ylabel("Predicted kWh"); plt.title("Potential Load-Shift Pairs")
    plt.tight_layout(); plt.savefig(FIGURES / "load_shift_simulation.png"); plt.close()

    plt.figure(figsize=(10, 4))
    if not daily.empty:
        plt.plot(daily["date"].astype(str), daily["estimated_savings"], marker="o")
        plt.xticks(rotation=45, ha="right")
    plt.ylabel("INR"); plt.title("Daily Potential Simulated Savings")
    plt.tight_layout(); plt.savefig(FIGURES / "daily_savings.png"); plt.close()

    plt.figure(figsize=(6, 4))
    forecast["demand_level"].value_counts().reindex(["Normal", "High", "Critical"], fill_value=0).plot.bar()
    plt.ylabel("Hours"); plt.title("Demand Severity Distribution")
    plt.tight_layout(); plt.savefig(FIGURES / "demand_severity_distribution.png"); plt.close()


def main() -> None:
    METRICS.mkdir(parents=True, exist_ok=True)
    historical = pd.read_parquet(ROOT / "data" / "processed" / "uci_hourly_clean.parquet")
    predictions = _load_predictions()
    selected_path = METRICS / "final_selected_model.json"
    selected = json.loads(selected_path.read_text(encoding="utf-8")) if selected_path.exists() else {}
    threshold = float(selected.get("p90_threshold", historical["energy_kwh"].quantile(.90)))
    critical = float(historical["energy_kwh"].quantile(.99))
    config = TOUConfig()
    forecast = build_peak_demand_forecast(predictions, threshold, critical)
    forecast.to_csv(METRICS / "peak_demand_forecast.csv", index=False)
    insights = energy_insights(historical, threshold)
    json_dump(METRICS / "energy_insights.json", insights)
    costs = calculate_tou_cost(forecast.rename(columns={"predicted_consumption": "consumption_kwh"}), config)
    costs.to_csv(METRICS / "tou_cost_analysis.csv", index=False)
    summary = {"tariff_label": "Illustrative TOU tariff used for simulation.", **{
        **{"off_peak_rate": config.off_peak_rate, "normal_rate": config.normal_rate, "peak_rate": config.peak_rate},
        **tou_summary(costs),
    }}
    json_dump(METRICS / "tou_summary.json", summary)
    shifts = recommend_load_shifts(predictions, threshold, .20, config)
    shifts.to_csv(METRICS / "load_shift_recommendations.csv", index=False)
    daily = daily_savings_analysis(
        forecast.rename(columns={"predicted_consumption": "consumption_kwh"}), shifts, config
    )
    daily.to_csv(METRICS / "daily_savings_analysis.csv", index=False)
    scenarios = []
    for fraction in (.10, .20, .30):
        scenario = recommend_load_shifts(predictions, threshold, fraction, config)
        baseline = float(costs["simulated_cost_inr"].sum())
        savings = float(scenario["estimated_savings"].sum())
        scenarios.append({
            "shiftable_fraction": fraction,
            "energy_shifted_kwh": float(scenario["shiftable_energy_kwh"].sum()),
            "simulated_savings_inr": savings,
            "savings_percentage": savings / baseline * 100 if baseline else 0.0,
        })
    pd.DataFrame(scenarios).to_csv(METRICS / "load_shift_sensitivity.csv", index=False)
    recommendations = generate_recommendations(historical, forecast, insights, threshold)
    baseline = float(costs["simulated_cost_inr"].sum())
    savings = float(shifts["estimated_savings"].sum())
    json_dump(METRICS / "smart_grid_summary.json", {
        "data_mode": "Historical forecast simulation",
        "historical_average_consumption": insights["average_hourly_consumption"],
        "forecast_average_consumption": float(forecast["predicted_consumption"].mean()),
        "peak_threshold": threshold,
        "critical_threshold": critical,
        "predicted_peak_count": int(forecast["is_peak"].sum()),
        "highest_predicted_demand": float(forecast["predicted_consumption"].max()),
        "highest_predicted_demand_timestamp": forecast.loc[forecast["predicted_consumption"].idxmax(), "timestamp"],
        "tou_baseline_cost": baseline,
        "potential_optimized_cost": baseline - savings,
        "potential_savings": savings,
        "potential_savings_percentage": savings / baseline * 100 if baseline else 0.0,
        "total_shiftable_energy": float(shifts["shiftable_energy_kwh"].sum()),
        "shiftable_fraction_assumption": .20,
        "recommendations": recommendations,
    })
    _save_figures(forecast, costs, shifts, daily, threshold, config)
    print("=" * 50)
    print("MODULE 9: SMART-GRID INSIGHTS")
    print("=" * 50)
    print("Status: PASS")
    print(f"Historical Average Consumption: {insights['average_hourly_consumption']:.4f} kWh/hour")
    print(f"Forecast Average Consumption: {forecast['predicted_consumption'].mean():.4f} kWh/hour")
    print(f"Peak Threshold: {threshold:.4f} kWh")
    print(f"Predicted Peak Count: {int(forecast['is_peak'].sum())}")
    print(f"Maximum Predicted Demand: {forecast['predicted_consumption'].max():.4f} kWh")
    print(f"Maximum Predicted Demand Time: {forecast.loc[forecast['predicted_consumption'].idxmax(), 'timestamp']}")
    print("\nTOU SIMULATION (illustrative, not an official tariff)")
    print(f"Rates INR/kWh: off-peak={config.off_peak_rate}, normal={config.normal_rate}, peak={config.peak_rate}")
    print(f"Baseline Simulated Cost: INR {baseline:.2f}")
    print("\nLOAD SHIFTING")
    print("Shiftable Fraction: 20% (assumed for simulation)")
    print(f"Total Potential Energy Shifted: {shifts['shiftable_energy_kwh'].sum():.4f} kWh")
    print(f"Potential Simulated Savings: INR {savings:.2f}")
    print(f"Potential Savings Percentage: {savings / baseline * 100 if baseline else 0.0:.2f}%")
    print("\nRECOMMENDATIONS")
    for item in recommendations:
        print(f"- [{item['priority']}] {item['recommendation']}")
    print("\nModule 10: NOT STARTED")


if __name__ == "__main__":
    main()
