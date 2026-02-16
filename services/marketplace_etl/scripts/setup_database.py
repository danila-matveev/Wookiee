"""
Database setup script.
Creates schemas, tables, and indexes from SQL files.
"""

import argparse
import os

from services.marketplace_etl.config.database import get_db_connection


def setup_database(recreate=False):
    """Create database schemas, tables, and indexes."""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    schema_file = os.path.join(base_dir, 'database', 'schema.sql')
    indexes_file = os.path.join(base_dir, 'database', 'indexes.sql')

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        if recreate:
            print("Dropping existing schemas...")
            cursor.execute("DROP SCHEMA IF EXISTS wb CASCADE")
            cursor.execute("DROP SCHEMA IF EXISTS ozon CASCADE")
            conn.commit()
            print("Schemas dropped.")

        print("Creating schemas and tables...")
        with open(schema_file) as f:
            cursor.execute(f.read())
        conn.commit()
        print("Schemas and tables created.")

        print("Creating indexes...")
        with open(indexes_file) as f:
            cursor.execute(f.read())
        conn.commit()
        print("Indexes created.")

        # Verify
        cursor.execute("""
            SELECT schemaname, tablename
            FROM pg_tables
            WHERE schemaname IN ('wb', 'ozon')
            ORDER BY schemaname, tablename
        """)
        tables = cursor.fetchall()
        print(f"\nCreated {len(tables)} tables:")
        for schema, table in tables:
            print(f"  {schema}.{table}")

    except Exception as e:
        conn.rollback()
        print(f"Error: {e}")
        raise
    finally:
        cursor.close()
        conn.close()


def main():
    parser = argparse.ArgumentParser(description='Setup Wookiee Database')
    parser.add_argument(
        '--recreate', action='store_true',
        help='Drop and recreate schemas (DESTRUCTIVE)'
    )
    args = parser.parse_args()

    if args.recreate:
        confirm = input("This will DROP all data. Type 'yes' to confirm: ")
        if confirm != 'yes':
            print("Aborted.")
            return

    setup_database(recreate=args.recreate)
    print("\nDatabase setup complete.")


if __name__ == '__main__':
    main()
