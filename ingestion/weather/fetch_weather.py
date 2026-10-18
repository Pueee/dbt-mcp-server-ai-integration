import logging
import os
import sys
import time
from datetime import date, datetime, timedelta, timezone

import pandas as pd
import requests

from load_weather import load_to_duckdb, get_last_loaded_date

# default values for the API parameters, can be overridden by environment variables
LATITUDE = os.getenv("LATITUDE", "51.45")
LONGITUDE = os.getenv("LONGITUDE", "-0.97")
LOCATION = os.getenv("LOCATION", "Reading")                                  
DEFAULT_START = date.fromisoformat(os.getenv("DEFAULT_START", "2026-07-01"))

URL = "https://archive-api.open-meteo.com/v1/archive"

params = {
    "latitude": LATITUDE,           # default: Reading                         
    "longitude": LONGITUDE,
    "daily": "temperature_2m_max,temperature_2m_min,wind_speed_10m_max",
    "timezone": "Europe/London",
}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger(__name__)


def fetch_daily_weather(params, max_retries=3):
    for attempt in range(1, max_retries + 1):
        try:
            response = requests.get(URL, params=params, timeout=30)
            response.raise_for_status()      # turns 4xx/5xx into an error
            log.info("Fetched %s to %s", params["start_date"], params["end_date"])
            return response.json()

        except requests.exceptions.RequestException as e:
            log.warning("Attempt %s of %s failed: %s", attempt, max_retries, e)
            if attempt == max_retries:
                log.error("Giving up after %s attempts", max_retries)
                raise                        # re-raise so the run is marked FAILED
            time.sleep(2 ** attempt)         # backoff: wait 2s, then 4s


# ---------- Main ----------

last_loaded = get_last_loaded_date(LOCATION)   # watermark for THIS location    
start = last_loaded + timedelta(days=1) if last_loaded else DEFAULT_START
end = date.today() - timedelta(days=5)         # archive API lags a few days

if start > end:
    log.info("%s: nothing new to load. Last loaded: %s", LOCATION, last_loaded)
    sys.exit(0)

params["start_date"] = start.isoformat()
params["end_date"] = end.isoformat()
log.info("%s: high-water mark %s. Loading %s to %s", LOCATION, last_loaded, start, end)

data = fetch_daily_weather(params)

df = pd.DataFrame(data["daily"])               # dict of lists -> one row per day
df = df.rename(columns={"time": "weather_date"})
df["weather_date"] = pd.to_datetime(df["weather_date"]).dt.date
df["latitude"] = data["latitude"]              # same value on every row
df["longitude"] = data["longitude"]
df["location"] = LOCATION                      
df["loaded_at"] = datetime.now(timezone.utc)   # insert timestamp, in UTC

log.info("Rows: %s", len(df))                  
load_to_duckdb(df, start, end, location=LOCATION)   # saves the whole range in one go

# FIX 4: leftover date_chunks test code removed

# Run for another place - always set ALL THREE together:                   
# LATITUDE=53.48 LONGITUDE=-2.24 LOCATION=Manchester python fetch_weather.py