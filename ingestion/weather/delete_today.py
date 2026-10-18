import duckdb
from load_weather import DB_PATH

con = duckdb.connect(DB_PATH)
sql_filter = "CAST(loaded_at AS DATE) = CURRENT_DATE"

print("Will delete:", con.execute(f"SELECT location, weather_date FROM raw.weather_daily WHERE {sql_filter}").fetchall())
con.execute(f"DELETE FROM raw.weather_daily WHERE {sql_filter}")
print("Rows now:", con.execute("SELECT COUNT(*) FROM raw.weather_daily").fetchone()[0])
con.close()