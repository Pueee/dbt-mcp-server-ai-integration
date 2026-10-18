import duckdb
from load_weather import DB_PATH

con = duckdb.connect(DB_PATH)
rows = con.execute("""
    SELECT location, MIN(weather_date), MAX(weather_date), COUNT(*)
    FROM raw.weather_daily
    GROUP BY location
    ORDER BY location
""").fetchall()
for r in rows:
    print(r)
con.close()