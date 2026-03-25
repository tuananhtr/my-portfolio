from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd
from sqlalchemy import create_engine

# Initialize the FastAPI app
app = FastAPI()

# --- CORS SETUP ---
# This is required so your frontend HTML file can talk to this backend
# without your browser blocking it for security reasons.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins (fine for local testing)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Connect to your SQLite database
DB_URL = "sqlite:///bds_data.db"
engine = create_engine(DB_URL)

@app.get("/")
def home():
    return {"message": "Welcome to the Real Estate API! Go to /api/properties to see the data."}

@app.get("/api/properties")
def get_properties():
    # 1. Query the database
    # We select the new 'dt' column along with the others, and make sure we only grab rows that actually have coordinates.
    query = """
        SELECT dt, Title, Price, Price_per_m2, Area, Latitude, Longitude, Project_Name, URL 
        FROM listings 
        WHERE Latitude IS NOT 'N/A' AND Longitude IS NOT 'N/A'
    """
    
    try:
        # Read the data into a Pandas DataFrame
        df = pd.read_sql(query, con=engine)
        
        # 2. Clean the coordinates
        # Ensure Latitude and Longitude are actual numbers, not strings
        df['Latitude'] = pd.to_numeric(df['Latitude'], errors='coerce')
        df['Longitude'] = pd.to_numeric(df['Longitude'], errors='coerce')
        
        # Drop any rows where the conversion failed
        df = df.dropna(subset=['Latitude', 'Longitude'])

        # 3. Return the data as a list of dictionaries (JSON format)
        return df.to_dict(orient="records")
        
    except Exception as e:
        return {"error": str(e)}