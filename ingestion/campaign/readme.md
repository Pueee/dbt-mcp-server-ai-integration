# Python ingestion (API → DuckDB → dbt)

Two pipelines load raw data into the project's DuckDB database. Python only extracts and loads. Flattening and modelling happen in dbt.

1. **Ad campaigns** from a local mock ad API (simulated, Meta-style). Feeds the `stg_api_ad_campaigns` dbt model.
2. **Weather** from the [Open-Meteo archive API](https://open-meteo.com/). A practice pipeline for incremental loads and backfills, with no dbt models yet.

## Ad campaigns

`campaign/fetch_adcampaigns.py` calls `/v1/campaigns` and loads every campaign into `raw.ad_campaigns` as raw JSON.

- **Auth:** a Bearer token read from the `AD_API_TOKEN` environment variable. There's no default, and the script stops if it isn't set.
- **Retries:** permanent errors (401, 403, 404) fail straight away. Temporary ones (timeouts, 5xx) are retried with exponential backoff, 2s then 4s.
- **Rate limits:** on a 429 the script reads the `Retry-After` header and waits that long before trying again. Tested by restarting the API with a limit of 2 calls a minute.
- **Pagination:** follows `paging.next` until it's absent. 10 campaigns arrive across 2 pages of 5.
- **Raw JSON:** each campaign is stored unchanged in a `payload` JSON column, with `id` and `loaded_at`. A new field from the API can't break the load; it waits in the payload until it's modelled.
- **Safe reruns:** delete by `id`, then insert, inside one transaction with rollback. Running it twice still gives 10 rows.

In dbt, `stg_api_ad_campaigns` pulls the fields out with `payload->>'field'` and casts the dates. It has `unique`, `not_null` and `accepted_values` tests. The singular test `assert_ad_campaign_keys_expected` fails if the API sends a JSON key it doesn't expect, such as a renamed field or a new one.

## Weather

- **Retries:** a 30-second timeout on each call, exponential backoff (2s, then 4s), and a re-raise after the last attempt so a failed run shows as failed.
- **Incremental loads:** the high-water mark is `MAX(weather_date)` per location, read from the target table, so it only moves after a load commits.
- **Safe reruns:** each load deletes and re-inserts its date range for that location inside one transaction.
- **Backfills:** `backfill_weather.py` loads history a week at a time, committing each week. Tested by forcing a crash mid-run: the committed weeks stayed, and the rerun resumed from the next day with no gaps or duplicates.
- **Several locations:** the grain is location + date. `migrate_add_location.py` is the one-off migration that added the column.
- **Schema changes:** before loading, incoming columns are compared with the table's. A new column is added with a warning, a missing optional column is loaded as NULL with a warning, and a missing required column stops the run.

## Files

| File | Purpose |
|---|---|
| `campaign/fetch_adcampaigns.py` | Ad API client: auth, retries, rate limits, pagination |
| `campaign/load_campaigns.py` | Loads campaigns into `raw.ad_campaigns` as JSON |
| `fetch_weather.py` | Loads weather since the last loaded date in one go |
| `backfill_weather.py` | Same, but in weekly chunks for long history |
| `load_weather.py` | DuckDB load, high-water mark and schema checks |
| `migrate_add_location.py` | One-off migration: adds `location` |
| `check_weather.py` | Row counts and date ranges per location |

## Running it

```bash
pip install requests pandas duckdb
```

Ad campaigns (the mock API must be running on port 8000; it isn't part of this repo):

```bash
cd ingestion/campaign
AD_API_TOKEN=<token> python fetch_adcampaigns.py
cd ../..
dbt build --select stg_api_ad_campaigns assert_ad_campaign_keys_expected
```

Weather, with Reading as the default location:

```bash
cd ingestion
python backfill_weather.py
```

To load another place, set all three variables:

```bash
LATITUDE=53.96 LONGITUDE=-1.08 LOCATION=York python backfill_weather.py
```

`fetch_weather.py` also reads `DEFAULT_START`, the first date to load for a new location (default `2026-07-01`).
