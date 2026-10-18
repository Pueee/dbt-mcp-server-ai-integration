import duckdb
from load_weather import DB_PATH

con = duckdb.connect(DB_PATH)
con.execute("ALTER TABLE raw.weather_daily ADD COLUMN location VARCHAR")
con.execute("UPDATE raw.weather_daily SET location = 'Reading'")
print(con.execute("SELECT location, COUNT(*) FROM raw.weather_daily GROUP BY location").fetchall())
con.close()