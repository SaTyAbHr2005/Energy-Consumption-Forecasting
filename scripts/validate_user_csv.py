import argparse
import sys
from pathlib import Path

# Add project root to path so we can import src
project_root = Path(__file__).resolve().parent.parent
sys.path.append(str(project_root))

from src.user_data_validator import validate_user_csv

def main():
    parser = argparse.ArgumentParser(description="Validate user uploaded household electricity CSV.")
    parser.add_argument("file_path", type=str, help="Path to the user CSV file")
    
    args = parser.parse_args()
    file_path = Path(args.file_path)
    
    result = validate_user_csv(file_path)
    
    print("\n" + "="*50)
    print("USER CSV VALIDATION REPORT")
    print("="*50)
    
    print(f"\nFile: {result.get('file_name', file_path.name)}")
    print(f"\nStatus: {result.get('status', 'INVALID')}\n")
    
    if result.get('errors'):
        print("ERRORS:")
        for error in result['errors']:
            print(f"  - {error}")
        print("\n" + "="*50)
        return

    print(f"Records: {result.get('records', 0)}")
    print(f"Columns: {result.get('columns', 0)}\n")
    
    print("Required columns:")
    for col in ['timestamp', 'energy_consumption']:
        if col in result.get('required_columns_present', []):
            print(f"  [x] {col}")
        else:
            print(f"  [ ] {col}")
    
    if result.get('start_timestamp') and result.get('end_timestamp'):
        print("\nDate range:")
        print(f"  Start: {result['start_timestamp']}")
        print(f"  End:   {result['end_timestamp']}")
        print(f"\nDuration: {result.get('duration_days', 0):.1f} days\n")
    
    if result.get('detected_interval'):
        print(f"Detected sampling interval: {result['detected_interval']}")
        print(f"Sampling consistency: {result.get('sampling_consistency', 0)}%\n")
    
    print(f"Duplicate timestamps: {result.get('duplicate_timestamps', 0)}")
    print(f"Detected gaps: {result.get('detected_gaps', 0)}\n")
    
    missing = result.get('missing_values', {})
    print("Missing values:")
    print(f"  timestamp: {missing.get('timestamp', 0)}")
    print(f"  energy_consumption: {missing.get('energy_consumption', 0)}\n")
    
    print(f"Negative consumption values: {result.get('negative_consumption_values', 0)}\n")
    
    stats = result.get('statistics', {})
    if stats:
        print("Consumption statistics:")
        print(f"  Minimum: {stats.get('min', 0):.2f} kWh")
        print(f"  Maximum: {stats.get('max', 0):.2f} kWh")
        print(f"  Mean: {stats.get('mean', 0):.2f} kWh")
        print(f"  Median: {stats.get('median', 0):.2f} kWh\n")
        
    print(f"Forecasting readiness: {str(result.get('forecasting_readiness', '')).upper()}\n")
    
    if result.get('warnings'):
        print("Warnings:")
        for warning in result['warnings']:
            print(f"  - {warning}")
            
    print("="*50)

if __name__ == "__main__":
    main()
