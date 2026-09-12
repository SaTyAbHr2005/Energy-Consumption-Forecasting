import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, Any

class UserDataValidator:
    def __init__(self, file_path: str | Path):
        self.file_path = Path(file_path)
        self.required_columns = ['timestamp', 'energy_consumption']
        
    def validate(self) -> Dict[str, Any]:
        result = {
            'file_name': self.file_path.name,
            'status': 'INVALID',
            'records': 0,
            'columns': 0,
            'required_columns_present': [],
            'extra_columns': [],
            'start_timestamp': None,
            'end_timestamp': None,
            'duration_days': 0,
            'detected_interval': None,
            'sampling_consistency': 0.0,
            'duplicate_timestamps': 0,
            'detected_gaps': 0,
            'missing_values': {'timestamp': 0, 'energy_consumption': 0},
            'negative_consumption_values': 0,
            'invalid_timestamps': 0,
            'invalid_energy_values': 0,
            'statistics': {},
            'forecasting_readiness': 'Unknown',
            'warnings': [],
            'errors': []
        }

        # 1. File Validation
        if not self.file_path.exists():
            result['errors'].append("File does not exist.")
            return result
        if not self.file_path.is_file():
            result['errors'].append("Path is not a file.")
            return result
        if self.file_path.suffix.lower() != '.csv':
            result['errors'].append("File is not a CSV.")
            return result
        if self.file_path.stat().st_size == 0:
            result['errors'].append("File is empty.")
            return result

        try:
            df = pd.read_csv(self.file_path)
        except Exception as e:
            result['errors'].append(f"Failed to parse CSV: {e}")
            return result
        
        if df.empty:
            result['errors'].append("CSV has no data rows.")
            return result

        result['records'] = len(df)
        result['columns'] = len(df.columns)

        # 2. Schema Validation
        columns_present = list(df.columns)
        for col in self.required_columns:
            if col in columns_present:
                result['required_columns_present'].append(col)
            else:
                result['errors'].append(f"Missing required column: {col}")
        
        result['extra_columns'] = [c for c in columns_present if c not in self.required_columns]

        if len(result['errors']) > 0:
            return result

        # 3. Timestamp Validation
        result['missing_values']['timestamp'] = int(df['timestamp'].isnull().sum())
        
        # Try parsing timestamps
        df['parsed_timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce')
        invalid_ts_count = int(df['parsed_timestamp'].isnull().sum()) - result['missing_values']['timestamp']
        result['invalid_timestamps'] = invalid_ts_count
        
        if invalid_ts_count > 0:
            result['errors'].append(f"Found {invalid_ts_count} invalid unparseable timestamps.")
            return result
            
        if result['missing_values']['timestamp'] > 0:
            result['errors'].append(f"Found {result['missing_values']['timestamp']} missing timestamps.")
            return result

        # Duplicates
        duplicate_count = int(df.duplicated(subset=['parsed_timestamp']).sum())
        result['duplicate_timestamps'] = duplicate_count
        if duplicate_count > 0:
            result['warnings'].append(f"{duplicate_count} duplicate timestamps detected.")

        # Sorting chronologically
        df = df.sort_values(by='parsed_timestamp').reset_index(drop=True)
        
        result['start_timestamp'] = df['parsed_timestamp'].min().strftime('%Y-%m-%d %H:%M:%S')
        result['end_timestamp'] = df['parsed_timestamp'].max().strftime('%Y-%m-%d %H:%M:%S')
        
        duration = df['parsed_timestamp'].max() - df['parsed_timestamp'].min()
        result['duration_days'] = duration.total_seconds() / (24 * 3600)

        # 4. Energy Consumption Validation
        result['missing_values']['energy_consumption'] = int(df['energy_consumption'].isnull().sum())
        
        df['parsed_energy'] = pd.to_numeric(df['energy_consumption'], errors='coerce')
        invalid_energy_count = int(df['parsed_energy'].isnull().sum()) - result['missing_values']['energy_consumption']
        result['invalid_energy_values'] = invalid_energy_count
        
        if invalid_energy_count > 0:
            result['errors'].append(f"Found {invalid_energy_count} invalid non-numeric energy values.")
            
        negative_count = int((df['parsed_energy'] < 0).sum())
        result['negative_consumption_values'] = negative_count
        
        if negative_count > 0:
            result['errors'].append(f"Found {negative_count} negative energy consumption values.")

        if len(result['errors']) > 0:
            return result

        # 5. Detect Sampling Interval and Gaps
        unique_ts = df['parsed_timestamp'].drop_duplicates().sort_values()
        if len(unique_ts) > 1:
            diffs = unique_ts.diff().dropna()
            
            # Find the most common interval
            mode_diff = diffs.mode()
            if not mode_diff.empty:
                common_interval = mode_diff.iloc[0]
                result['detected_interval'] = str(common_interval).split()[-1] if 'days' not in str(common_interval) else str(common_interval)
                
                # Consistency
                consistent_count = (diffs == common_interval).sum()
                result['sampling_consistency'] = round((consistent_count / len(diffs)) * 100, 2)
                
                if result['sampling_consistency'] < 100:
                    result['warnings'].append(f"Sampling consistency is {result['sampling_consistency']}%.")
                
                # Gaps (differences larger than the common interval)
                gaps = (diffs > common_interval).sum()
                result['detected_gaps'] = int(gaps)
                if gaps > 0:
                    result['warnings'].append(f"{gaps} timestamp gaps detected.")
        else:
            result['detected_interval'] = "N/A"
            result['sampling_consistency'] = 100.0
            
        # 6. Basic dataset metadata
        valid_energy = df['parsed_energy'].dropna()
        if not valid_energy.empty:
            result['statistics'] = {
                'min': float(valid_energy.min()),
                'max': float(valid_energy.max()),
                'mean': float(valid_energy.mean()),
                'median': float(valid_energy.median())
            }
            
        # 7. Forecasting readiness
        days = result['duration_days']
        if days < 7:
            result['forecasting_readiness'] = 'Insufficient history'
            result['warnings'].append("Insufficient history for forecasting (less than 7 days).")
        elif days < 30:
            result['forecasting_readiness'] = 'Basic'
        elif days < 90:
            result['forecasting_readiness'] = 'Good'
        else:
            result['forecasting_readiness'] = 'Strong'

        # 8. Final Status
        if len(result['errors']) == 0:
            if len(result['warnings']) > 0:
                result['status'] = 'VALID_WITH_WARNINGS'
            else:
                result['status'] = 'VALID'

        return result

def validate_user_csv(file_path: str | Path) -> Dict[str, Any]:
    validator = UserDataValidator(file_path)
    return validator.validate()
