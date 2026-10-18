import duckdb
from load_campaigns import load_campaigns

DB_PATH = "D:/Puja Files/Learning/MCP/dbt_mcp_demo/dev.duckdb" # put your real path here

con = duckdb.connect(DB_PATH)

## Check the contents of the raw.ad_campaigns table
#It’s like JSON_VALUE(payload, '$.name') in SQL Server or BigQuery.
rows = con.execute("""
    SELECT id,
          payload->>'name'      AS name,  -- payload->>'name' means: from the JSON, pull out name as text.
          payload->>'objective' AS objective,
          payload->>'status'    AS status,
          payload->>'start_date' AS start_date,
          payload->>'end_date'   AS end_date,
          loaded_at
   FROM raw.ad_campaigns
   ORDER BY id
""").fetchall()
for r in rows:
    print(r)
con.close()