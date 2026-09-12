import os
import pandas as pd
from pathlib import Path

def inspect_dataset():
    """
    Inspects the downloaded UCI electricity dataset.
    Prints general info, basic statistics, and missing value counts.
    Does not modify the raw data.
    """
    project_root = Path(__file__).resolve().parent.parent
    data_file = project_root / 'data' / 'raw' / 'household_power_consumption.txt'
    
    if not data_file.exists():
        print(f"Error: Dataset not found at {data_file}")
        print("Please run scripts/download_dataset.py first.")
        return

    print("Loading dataset for inspection. This might take a moment...")
    try:
        # The dataset uses ';' as separator and '?' for missing values
        df = pd.read_csv(data_file, sep=';', low_memory=False, na_values=['?'])
        
        file_size_mb = data_file.stat().st_size / (1024 * 1024)
        
        print("\n" + "="*50)
        print("DATASET INSPECTION REPORT")
        print("="*50)
        print(f"File name: {data_file.name}")
        print(f"File size: {file_size_mb:.2f} MB")
        print(f"Number of records (rows): {len(df)}")
        print(f"Number of columns: {len(df.columns)}")
        print(f"\nColumn names:\n{list(df.columns)}")
        
        print("\n--- First 5 records ---")
        print(df.head())
        
        print("\n--- Last 5 records ---")
        print(df.tail())
        
        print("\n--- Data types ---")
        print(df.dtypes)
        
        print("\n--- Number of missing values per column ---")
        print(df.isnull().sum())
        
        # Approximate date range
        if 'Date' in df.columns:
            # Assuming Date is in dd/mm/yyyy format based on UCI documentation
            df['Date_Parsed'] = pd.to_datetime(df['Date'], format='%d/%m/%Y', errors='coerce')
            min_date = df['Date_Parsed'].min()
            max_date = df['Date_Parsed'].max()
            print(f"\nApproximate date range: {min_date.date()} to {max_date.date()}")
            
        print("\n--- Basic descriptive statistics for numeric columns ---")
        # Only show stats for numeric columns
        numeric_cols = df.select_dtypes(include=['float64', 'int64']).columns
        if not numeric_cols.empty:
            print(df[numeric_cols].describe().T)
        else:
            print("No numeric columns found to summarize.")
            
    except Exception as e:
        print(f"An error occurred while inspecting the dataset: {e}")

if __name__ == "__main__":
    inspect_dataset()
