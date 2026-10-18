import logging
import duckdb


log = logging.getLogger(__name__)

DB_PATH = "../dev.duckdb"    # put your real path here


def load_to_duckdb(df, start_date, end_date, location="Reading"):
    con = duckdb.connect(DB_PATH)
    try:
        con.execute("CREATE SCHEMA IF NOT EXISTS raw")
        con.execute("""
            CREATE TABLE IF NOT EXISTS raw.weather_daily (
                weather_date        DATE,
                temperature_2m_max  DOUBLE,
                temperature_2m_min  DOUBLE,
                precipitation_sum   DOUBLE,
                latitude            DOUBLE,
                longitude           DOUBLE,
                location            VARCHAR,  -- added location column to the table
                loaded_at           TIMESTAMPTZ
            )
        """)
#--schema drift handling: check if the table has all the columns that the source sent, and add any new columns to the table
        table_cols = get_table_columns(con)
        df_cols = set(df.columns)
        new_cols = df_cols - table_cols
        missing_cols = table_cols - df_cols

        REQUIRED = {"weather_date", "location", "loaded_at"}
        missing_required = missing_cols & REQUIRED
        if missing_required:
            raise RuntimeError(f"Schema change: required columns missing {missing_required}")

        for col in missing_cols - REQUIRED:
            df[col] = None
            log.warning(f"Schema change: source no longer sends {col}. Loading NULL - check dbt models.")

        for col in new_cols:
            con.execute(f'ALTER TABLE raw.weather_daily ADD COLUMN "{col}" DOUBLE')
            log.warning(f"Schema change: added new column {col}. You may want to update the dbt model.")

        con.register("new_rows", df)

        con.execute("BEGIN TRANSACTION")
        con.execute(
            "DELETE FROM raw.weather_daily WHERE weather_date BETWEEN ? AND ? And location = ?",
            [start_date, end_date, location],
        )

        cols = ", ".join(f'"{c}"' for c in df.columns)
        con.execute(f"""
                    INSERT INTO raw.weather_daily ({cols})
                    SELECT {cols} FROM new_rows
                """)
        con.execute("COMMIT")

        total = con.execute("SELECT COUNT(*) FROM raw.weather_daily").fetchone()[0]
        log.info("Loaded %s rows. Table now has %s rows", len(df), total)

    except Exception:
        con.execute("ROLLBACK")
        raise
    finally:
        con.close()

#---------- Functions ----------
def get_last_loaded_date(location="Reading"):
    con = duckdb.connect(DB_PATH)
    try:
        return con.execute(
            "SELECT MAX(weather_date) FROM raw.weather_daily WHERE location = ?",
            [location]
        ).fetchone()[0]
    except duckdb.CatalogException:      # table doesn't exist yet (first run)
        return None
    finally:
        con.close()

#---------- Function-2 ----------
def get_table_columns(con):
    rows = con.execute("""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'raw' AND table_name = 'weather_daily'
    """).fetchall()
    return {row[0] for row in rows}