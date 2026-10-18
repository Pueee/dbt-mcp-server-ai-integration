import logging
import sys
import time
from datetime import date, datetime, timedelta, timezone

import pandas as pd
import requests
from load_weather import load_to_duckdb, get_last_loaded_date

import os

#default values for the API parameters, can be overridden by environment variables
LATITUDE = os.getenv("LATITUDE", "51.45")
LONGITUDE = os.getenv("LONGITUDE", "-0.97")
LOCATION = os.getenv("LOCATION", "Reading")

# ---------- Settings ----------
URL = "https://archive-api.open-meteo.com/v1/archive"

DEFAULT_START = date(2026, 7, 1)     # used only when the table is empty

params = {  #dictionary of parameters to be passed to the API
    "latitude": float(LATITUDE),
    "longitude": float(LONGITUDE),
    "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum",
    "timezone": "Europe/London",
}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger(__name__)


# ---------- Functions ----------
def fetch_daily_weather(params, max_retries=3):
    for attempt in range(1, max_retries + 1):
        try:
            response = requests.get(URL, params=params, timeout=30)  #calls the api with the given parameters and a timeout of 30 seconds
            response.raise_for_status() # turns 4xx/5xx into an error like 404 or 500 server error or connection error
            #log.info("Fetched %s to %s", params["start_date"], params["end_date"])
            log.info(f"Fetched {params['start_date']} to {params['end_date']}")
            return response.json()
        except requests.exceptions.RequestException as e:
            #log.warning("Attempt %s of %s failed: %s", attempt, max_retries, e)
            log.warning(f"Attempt {attempt} of {max_retries} failed: {e}")
            if attempt == max_retries: #check if this is the last attempt
                log.error("Giving up after %s attempts", max_retries)
                raise
            time.sleep(2 ** attempt)  # exponential backoff: wait 2s, then 4s, then 8s


def date_chunks(start, end, days=7):  #same concept as in stored proc fetch next from cursor @start_date, @end_date, @days = 7
    chunk_start = start
    while chunk_start <= end:
        chunk_end = min(chunk_start + timedelta(days=days - 1), end)
        yield chunk_start, chunk_end  #yield means return the value and pause the function, so that it can be resumed later. This is useful for generating a sequence of values over time, rather than all at once.
        chunk_start = chunk_end + timedelta(days=1)


# ---------- Main ----------
#define variables
last_loaded = get_last_loaded_date() #this gets value from python function get_last_loaded_date() which is defined in load_weather.py file. It returns the last date for which data was loaded into the database.
start = last_loaded + timedelta(days=1) if last_loaded else DEFAULT_START
end = date.today() - timedelta(days=5)        # archive API lags a few days

#script starts
if start > end:
    log.info("Nothing new to load. Last loaded: %s", last_loaded)
    sys.exit(0)

log.info("High-water mark: %s. Backfilling %s to %s", last_loaded, start, end)

for chunk_start, chunk_end in date_chunks(start, end):  #calling the function
    params["start_date"] = chunk_start.isoformat()
    params["end_date"] = chunk_end.isoformat()

    data = fetch_daily_weather(params)  #passes params chunkstart and chunkend to the function fetch_daily_weather() which calls the API and returns the data in json format

    df = pd.DataFrame(data["daily"])  #convert the daily weather data to a pandas DataFrame
    df = df.rename(columns={"time": "weather_date"})
    df["weather_date"] = pd.to_datetime(df["weather_date"]).dt.date
    df["latitude"] = data["latitude"]
    df["longitude"] = data["longitude"]
    df["loaded_at"] = datetime.now(timezone.utc)

    load_to_duckdb(df, chunk_start, chunk_end)     #calls the function and saves this week only

log.info("Backfill complete")
#script ends