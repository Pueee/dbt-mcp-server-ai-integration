import requests
import pandas as pd

URL = "https://archive-api.open-meteo.com/v1/archive"

params = {
    "latitude": 51.45,                 # Reading
    "longitude": -0.97,
    "start_date": "2026-10-01",
    "end_date": "2026-10-03",          # just 3 days, enough to look
    "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum,wind_speed_10m_max",
    "timezone": "Europe/London",
}

response = requests.get(URL, params=params, timeout=30)
response.raise_for_status()
data = response.json()

# 1. What the API sent (the keys inside "daily")
print("API sent:", list(data["daily"].keys()))

# 2. What the DataFrame looks like
df = pd.DataFrame(data["daily"])
print("DataFrame columns:", df.columns.tolist())
print(df)