# Spark Processing (R / sparklyr)

## Overview
This document describes the Big Data processing layer (Module 3) built using Apache Spark through R's `sparklyr` package. 
The purpose of this module is to demonstrate scalable distributed data ingestion, processing, and aggregation for the large UCI household electricity dataset (over 2 million records).

## Why Spark?
Base R data frames are excellent for small to medium datasets and are used in Module 2 for validating single-household user CSV uploads, but they require the entire dataset to reside in RAM. The UCI dataset is relatively large and serves as our proxy for Big Data. Spark allows for distributed in-memory processing, making it suitable for out-of-core processing and preparing the project to scale out to cluster environments if necessary.

## Spark Processing Pipeline

```text
Raw UCI Dataset
      |
      v
Spark DataFrame (sparklyr)
      |
      v
Schema + Timestamp
      |
      v
Missing Value Analysis
      |
      v
Energy Conversion
      |
      v
Hourly Aggregation
      |
      v
Parquet
```

### 1. SparkSession
The stage opens a local Spark session with `sparklyr::spark_connect()` configured for timezone-aware execution in UTC. 
This avoids local Windows/Java timestamp discrepancy issues.

### 2. Explicit Schema
Rather than relying on schema inference, `spark_read_csv()` is given an explicit column-type map. The data includes the character `?` to represent missing numerical values. Setting `null_value = "?"` allows Spark to seamlessly convert these characters into SQL `NULL`s, preventing column type downgrade from `DoubleType` to `StringType`.

### 3. Timestamp Construction
The raw data contains discrete `Date` and `Time` columns as strings. We construct a single native Spark `TimestampType` using `concat_ws` and `to_timestamp`. This is essential for time-based window aggregations.

### 4. Missing-Value Analysis
We use Spark SQL aggregations to calculate the count of missing (`NULL`) values for each numeric column in a distributed manner, avoiding collecting the whole dataset into the R session.

### 5. kW to kWh Conversion
The target column for forecasting is `energy_consumption` (kWh). The UCI dataset contains `Global_active_power` representing minute-averaged active power in kilowatts (kW). 
We derive a new column:
`energy_kwh = Global_active_power / 60`
This calculation converts the minute-rate power to the actual energy consumed during that 1-minute interval.

### 6. Hourly Aggregation
Using Spark's `date_trunc` function, the data is aggregated into hourly windows. 
- Extensively instantaneous quantities (Voltage, Global_intensity) are averaged.
- Cumulative quantities (energy_kwh, sub-meterings) are summed.

### 7. Parquet Storage
The resulting aggregated dataset is collected (about 35k rows) and written to `data/processed/uci_hourly.parquet` in **Parquet** format with the `arrow` package. Parquet is a columnar storage format heavily optimized for analytical queries and is the standard for Big Data workflows.

## User CSV vs UCI Data
- **UCI Data**: Ingested via `spark_hourly_aggregate()` (`backend/pipeline/R/spark_stages.R`), heavily transformed to synthesize timestamps, map missing values, and convert power to energy.
- **User CSV Data**: Validated and hourly-summed by the API (`backend/R/validator.R`, `backend/R/analysis.R`), representing a much simpler, pre-validated schema (`timestamp`, `energy_consumption`). 
Both paths ultimately align into compatible aggregated DataFrames (like hourly resolution) for downstream modules to consume uniformly.

## Execution
Run the Spark processing pipeline locally from the project root:
```bash
Rscript backend/pipeline/02_spark_hourly.R
```

Spark needs Java 8/11/17. The `Dockerfile.pipeline` image bundles R, Java and Spark, so nothing has to be installed by hand (see the README).
