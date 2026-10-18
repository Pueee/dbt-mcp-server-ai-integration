# Weather ingestion (Python → DuckDB)

Pulls daily weather from the [Open-Meteo archive API](https://open-meteo.com/) and loads it into `raw.weather_daily` in the project's DuckDB database, where the dbt project picks it up.

## What it handles

- **Retries:** a 30-second timeout on each call, exponential backoff (2s, then 4s), and a re-raise after the last attempt so a failed run shows as failed.
- **Incremental loads:** the high-water mark is `MAX(weather_date)` per location, read from the target table, so it only moves after a load commits.
- **Safe reruns:** each load deletes and re-inserts its date range for that location inside one transaction. Running it twice gives the same result.
- **Backfills:** `backfill_weather.py` loads history a week at a time, committing each week. Tested by forcing a crash mid-run: the committed weeks stayed and the rerun resumed from the next day with no gaps or duplicates.
- **Several locations:** the grain is location + date. `migrate_add_location.py` is the one-off migration that added the column to the existing table.
- **Schema changes:** before loading, incoming columns are compared with the table's. A new column is added with a warning, a missing optional column is loaded as NULL with a warning, and a missing required column stops the run.

## Files

| File | Purpose |
|---|---|
| `fetch_weather.py` | Loads everything since the last loaded date in one go |
| `backfill_weather.py` | Same, but in weekly chunks for long history |
| `load_weather.py` | DuckDB load, high-water mark and schema checks |
| `migrate_add_location.py` | One-off migration: adds `location` |
| `check_weather.py` | Row counts and date ranges per location |

## Running it

```bash
pip install requests pandas duckdb
cd ingestion
python backfill_weather.py
```

Settings come from environment variables, with Reading as the default. To load another place, set all three:

```bash
LATITUDE=53.96 LONGITUDE=-1.08 LOCATION=York python backfill_weather.py
```

`fetch_weather.py` also reads `DEFAULT_START`, the first date to load for a new location (default `2026-07-01`).
