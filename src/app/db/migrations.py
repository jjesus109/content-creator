import logging
from pathlib import Path

import psycopg2

from app.settings import get_settings

logger = logging.getLogger(__name__)

# Resolved once at import time — migrations/ sits at the project root (4 levels up from this file)
MIGRATIONS_DIR = Path(__file__).resolve().parents[3] / "migrations"


def _get_dsn() -> str:
    # psycopg2 expects postgresql:// not postgresql+psycopg2://
    return get_settings().database_url.replace("postgresql+psycopg2://", "postgresql://", 1)


def run_migrations() -> None:
    """
    Apply any pending SQL migrations in migrations/ on startup.

    Tracks applied migrations in a schema_migrations table (created automatically).
    Files are applied in filename order (0001_..., 0002_..., etc.).
    Each migration runs in its own transaction — a failure rolls back that file only.
    """
    dsn = _get_dsn()
    conn = psycopg2.connect(dsn)
    conn.autocommit = False

    try:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version     text PRIMARY KEY,
                    applied_at  timestamptz DEFAULT now() NOT NULL
                )
            """)
            conn.commit()

            cur.execute("SELECT version FROM schema_migrations ORDER BY version")
            applied = {row[0] for row in cur.fetchall()}

        sql_files = sorted(MIGRATIONS_DIR.glob("*.sql"))
        pending = [f for f in sql_files if f.name not in applied]

        if not pending:
            logger.info("Migrations: all up to date (%d applied).", len(applied))
            return

        logger.info("Migrations: %d pending, %d already applied.", len(pending), len(applied))

        for sql_file in pending:
            logger.info("Applying migration: %s", sql_file.name)
            sql = sql_file.read_text(encoding="utf-8")
            try:
                with conn.cursor() as cur:
                    cur.execute(sql)
                    cur.execute(
                        "INSERT INTO schema_migrations (version) VALUES (%s)",
                        (sql_file.name,),
                    )
                conn.commit()
                logger.info("Migration applied: %s", sql_file.name)
            except Exception:
                conn.rollback()
                logger.exception("Migration failed: %s — rolled back.", sql_file.name)
                raise

    finally:
        conn.close()
