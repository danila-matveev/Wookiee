"""Delete old records from istoriya_izmeneniy (180-day retention)."""
import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()


def main():
    conn = psycopg2.connect(
        host=os.getenv("SUPABASE_HOST"),
        port=int(os.getenv("SUPABASE_PORT", "5432")),
        database=os.getenv("SUPABASE_DB", "postgres"),
        user=os.getenv("SUPABASE_USER"),
        password=os.getenv("SUPABASE_PASSWORD"),
    )
    cur = conn.cursor()
    cur.execute("""
        DELETE FROM istoriya_izmeneniy
        WHERE data_izmeneniya < now() - interval '180 days'
    """)
    deleted = cur.rowcount
    conn.commit()
    conn.close()
    print(f"Retention cleanup: deleted {deleted} records older than 180 days")


if __name__ == "__main__":
    main()
