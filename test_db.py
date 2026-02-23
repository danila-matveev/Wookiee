import os
import psycopg2

DB_CONFIG = {
    "host": "89.23.119.253",
    "port": 6433,
    "user": "wookiee_client",
    "password": "cqpy1jyMSVsDWqzQzfJhOG0I",
    "database": "pbi_wb_wookiee"
}

def test():
    print("Starting test...")
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        print("Connected.")
        cur = conn.cursor()
        cur.execute("SELECT 1")
        print("Select 1:", cur.fetchone())
        
        query = "SELECT article, SUM(reclama), SUM(reclama_vn) FROM abc_date WHERE date = '2026-02-19' AND article ILIKE 'ruby%' GROUP BY 1"
        cur.execute(query)
        rows = cur.fetchall()
        print("Rows:", rows)
        cur.close()
        conn.close()
    except Exception as e:
        print("ERROR:", e)

if __name__ == "__main__":
    test()
