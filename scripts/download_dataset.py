import os
import requests
import zipfile
from pathlib import Path

def download_dataset():
    """
    Downloads the official UCI Individual Household Electric Power Consumption dataset,
    extracts the raw text file to the data/raw/ directory, and handles errors.
    """
    # Define paths
    project_root = Path(__file__).resolve().parent.parent
    raw_data_dir = project_root / 'data' / 'raw'
    raw_data_dir.mkdir(parents=True, exist_ok=True)
    
    zip_path = raw_data_dir / 'household_power_consumption.zip'
    extract_path = raw_data_dir
    data_file = raw_data_dir / 'household_power_consumption.txt'
    
    url = "https://archive.ics.uci.edu/static/public/235/individual+household+electric+power+consumption.zip"
    
    # Check if the extracted file already exists
    if data_file.exists():
        print(f"Dataset already exists at {data_file}. Skipping download.")
        return

    print(f"Downloading dataset from {url}...")
    try:
        response = requests.get(url, stream=True)
        response.raise_for_status()
        
        with open(zip_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        print("Download completed.")
        
        print(f"Extracting dataset to {extract_path}...")
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(extract_path)
        print("Extraction completed.")
        
        if zip_path.exists():
            zip_path.unlink()
            print("Removed temporary zip file.")
            
        if data_file.exists():
            print(f"Success! Dataset is ready at {data_file}")
        else:
            print("Warning: Expected data file not found after extraction.")
            
    except requests.exceptions.RequestException as e:
        print(f"Error downloading dataset: {e}")
    except zipfile.BadZipFile:
        print("Error: The downloaded file is not a valid zip file.")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    download_dataset()
