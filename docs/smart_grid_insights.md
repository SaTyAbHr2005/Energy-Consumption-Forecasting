# Module 9: Smart-Grid Insights and Recommendations

## Purpose

Module 9 turns the selected forecasting output into forecast-based decision
support. It reports historical measured consumption separately from predicted
consumption and from illustrative tariff and load-shifting simulations. It does
not provide live smart-meter monitoring, appliance control, or automatic
load shifting.

The Big Data Analytics pipeline is:

```text
2,075,259 raw minute-level records
        -> Spark (sparklyr)
34,589 hourly observations
        -> preprocessing and feature engineering
        -> forecasting
        -> peak-demand analytics
        -> TOU simulation
        -> load-shifting analysis
        -> cost/savings estimation
        -> decision support
```

## Peak Demand Detection

The selected model metadata supplies the established 90th-percentile
high-demand threshold (`p90_threshold`, currently 2.345 kWh). A forecast is a
peak when `predicted_consumption >= threshold`, and the threshold is
configurable.

## Demand Severity

`Normal` is below the high-demand threshold, `High` is at least that threshold
but below the critical threshold, and `Critical` is at least the historical
99th-percentile threshold. The critical threshold is calculated from the
historical hourly data unless a future reusable project threshold is supplied.

## TOU Pricing Simulation

The default periods are off-peak 00:00-06:00 and 22:00-00:00, normal
06:00-17:00, and peak 17:00-22:00. Rates are configurable and the defaults
(INR 3, 6, and 10 per kWh) are explicitly an **Illustrative TOU tariff used
for simulation**, not an official electricity-provider tariff.

## Load Shifting and Shiftable Fraction

The engine pairs forecast peak hours with lower-demand, non-peak hours only
when the destination has a lower simulated rate. It shifts only the excess
above the high-demand threshold and caps it at a configurable fraction of
source and destination consumption. The default is 20%. The dataset has no
appliance flexibility labels, so 100% shiftability cannot be assumed.

## Cost and Savings

Baseline simulated cost applies the illustrative tariff to the original
forecast schedule. Potential optimized cost subtracts the cost difference for
accepted shifts. Savings are **estimated/potential simulated savings**, not a
guarantee or an actual electricity bill.

## Recommendation Engine

Rules use calculated conditions: forecast evening demand at/above the
threshold, repeated forecast peaks, measured weekend-vs-weekday differences,
and unusually high overnight measured demand. Recommendations include a
priority, reason, and supporting metric; they do not make unsupported
appliance-specific claims.

## Sensitivity Analysis

The execution script evaluates 10%, 20%, and 30% shiftable-fraction scenarios
in `load_shift_sensitivity.csv`, reporting energy shifted, simulated savings,
and savings percentage.

## Limitations

* No live smart-meter connection; the UCI run is a historical forecast simulation.
* No appliance-level data or automatic appliance control.
* TOU prices are simulated and not official tariffs.
* The shiftable fraction is an assumption, not measured flexibility.
* Savings are estimated and are not guaranteed.
* Forecast uncertainty affects every recommendation.

