import logging
import duckdb

log = logging.getLogger(__name__)

DB_PATH = "D:/Puja Files/Learning/MCP/dbt_mcp_demo/dev.duckdb" # put your real path here

def load_campaigns(df):
    con = duckdb.connect(DB_PATH)
    try:
        con.execute("CREATE SCHEMA IF NOT EXISTS raw")
        con.execute("""
            CREATE TABLE IF NOT EXISTS raw.ad_campaigns (
                id                  VARCHAR,
                payload             JSON,
                loaded_at           TIMESTAMPTZ
            )
        """)
        con.register("new_rows", df)

        con.execute("BEGIN TRANSACTION")
        con.execute(
            "DELETE FROM raw.ad_campaigns WHERE id IN (SELECT id FROM new_rows)"
        )

        cols = ", ".join(f'"{c}"' for c in df.columns)
        con.execute(f"""
                    INSERT INTO raw.ad_campaigns ({cols})
                    SELECT {cols} FROM new_rows
                """)
        
        con.execute("COMMIT")

        total = con.execute("SELECT COUNT(*) FROM raw.ad_campaigns").fetchone()[0]
        log.info(f"Total campaigns loaded into database: {total}")

    except Exception: #try-except block to handle any exceptions that may occur during the execution of the code within the try block. If an exception occurs, the code within the except block will be executed.
           con.execute("ROLLBACK")
           raise
    
    finally:
        con.close()
