"""Migration 004: Add status_id column to modeli_osnova table.

Allows filtering model osnova records by status (Продается, Архив, etc.)
in the same way modeli (child variations) can be filtered.
"""


def upgrade(connection) -> None:
    """Add status_id FK column to modeli_osnova."""
    connection.execute(
        "ALTER TABLE modeli_osnova ADD COLUMN IF NOT EXISTS status_id INTEGER REFERENCES statusy(id);"
    )


def downgrade(connection) -> None:
    """Remove status_id column from modeli_osnova."""
    connection.execute(
        "ALTER TABLE modeli_osnova DROP COLUMN IF EXISTS status_id;"
    )
