import pandas as pd
from sqlalchemy import create_engine
import os

# --- 1. Setup the File Paths ---
# This ensures Python always finds the database no matter where your terminal is
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(SCRIPT_DIR, "bds_data.db")

# This is where the output JSON file will be saved
JSON_EXPORT_PATH = os.path.join(SCRIPT_DIR, "hcm_real_estate_data.json") 

# --- 2. Connect to the Database ---
DB_URL = f"sqlite:///{DB_PATH}"
engine = create_engine(DB_URL)

def export_database():
    print(f"Reading database from: {DB_PATH}")
    
    try:
        # 1. Query the Data
        query = "SELECT * FROM listings" 
        df = pd.read_sql(query, con=engine)
        
        # 2. CLEAN THE DATA
        # Drop rows missing GPS coordinates
        df = df.dropna(subset=['Latitude', 'Longitude', 'Price_per_m2'])
        
        # Ensure Price_per_m2 is a number, forcing errors to NaN
        df['Price_per_m2'] = pd.to_numeric(df['Price_per_m2'], errors='coerce')
        
        # THE SHIELD: Keep only rows where the Price_per_m2 is less than 500 Million VND
        df = df[df['Price_per_m2'] < 500000000]
        
        # 3. Export to JSON
        df.to_json(JSON_EXPORT_PATH, orient="records", force_ascii=False, indent=4)
        print(f"Success! Exported {len(df)} cleaned rows to {JSON_EXPORT_PATH}")
        
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    export_database()