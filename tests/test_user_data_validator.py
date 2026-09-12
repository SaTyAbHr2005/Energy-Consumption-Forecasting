import pytest
from pathlib import Path
import sys

project_root = Path(__file__).resolve().parent.parent
sys.path.append(str(project_root))

from src.user_data_validator import validate_user_csv

FIXTURES_DIR = Path(__file__).parent / 'fixtures'

def test_valid_csv():
    result = validate_user_csv(FIXTURES_DIR / 'sample_valid_energy.csv')
    assert result['status'] == 'VALID'
    assert result['records'] == 3000
    assert result['columns'] == 2
    assert result['negative_consumption_values'] == 0
    assert result['invalid_energy_values'] == 0
    assert result['invalid_timestamps'] == 0
    assert result['duplicate_timestamps'] == 0
    assert result['detected_gaps'] == 0
    assert result['forecasting_readiness'] == 'Good'

def test_invalid_schema():
    result = validate_user_csv(FIXTURES_DIR / 'sample_invalid_schema.csv')
    assert result['status'] == 'INVALID'
    assert any('Missing required column' in err for err in result['errors'])

def test_invalid_values():
    result = validate_user_csv(FIXTURES_DIR / 'sample_invalid_values.csv')
    assert result['status'] == 'INVALID'
    assert result['negative_consumption_values'] == 1
    # 'abc' is 1 invalid, None is 1 missing.
    assert result['invalid_energy_values'] == 1
    assert result['missing_values']['energy_consumption'] == 1
    assert any('negative energy' in err for err in result['errors'])

def test_short_history():
    result = validate_user_csv(FIXTURES_DIR / 'sample_short_history.csv')
    assert result['status'] == 'VALID_WITH_WARNINGS'
    assert result['forecasting_readiness'] == 'Insufficient history'
    assert any('Insufficient history' in warn for warn in result['warnings'])

def test_gaps_and_duplicates():
    result = validate_user_csv(FIXTURES_DIR / 'sample_gaps_duplicates.csv')
    assert result['status'] == 'VALID_WITH_WARNINGS'
    assert result['duplicate_timestamps'] == 1
    assert result['detected_gaps'] == 1
    assert any('duplicate' in warn for warn in result['warnings'])
    assert any('gap' in warn for warn in result['warnings'])

def test_file_not_found():
    result = validate_user_csv(FIXTURES_DIR / 'does_not_exist.csv')
    assert result['status'] == 'INVALID'
    assert any('File does not exist' in err for err in result['errors'])
