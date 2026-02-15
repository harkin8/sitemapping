"""PostgreSQL connection and query helpers."""

import os
import psycopg2
from psycopg2.extras import RealDictCursor
from contextlib import contextmanager

DATABASE_URL = os.environ.get("DATABASE_URL", "")


def get_connection():
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)


@contextmanager
def get_db():
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    """Create tables if they don't exist."""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS campaigns (
                id              TEXT PRIMARY KEY,
                name            TEXT NOT NULL,
                status          TEXT DEFAULT 'created',
                created_by      TEXT,
                created_at      TIMESTAMPTZ DEFAULT NOW(),
                updated_at      TIMESTAMPTZ DEFAULT NOW()
            );

            CREATE TABLE IF NOT EXISTS campaign_accounts (
                id              BIGSERIAL PRIMARY KEY,
                campaign_id     TEXT NOT NULL REFERENCES campaigns(id),
                account_name    TEXT NOT NULL,
                domain          TEXT,
                account_id      TEXT,
                clay_import_status TEXT DEFAULT 'pending'
            );
            CREATE INDEX IF NOT EXISTS idx_campaign_accounts
                ON campaign_accounts(campaign_id);

            CREATE TABLE IF NOT EXISTS enriched_people (
                id              BIGSERIAL PRIMARY KEY,
                campaign_id     TEXT NOT NULL REFERENCES campaigns(id),
                account_name    TEXT,
                account_id      TEXT,
                first_name      TEXT,
                last_name       TEXT,
                full_name       TEXT,
                job_title       TEXT,
                persona         TEXT,
                persona_score   TEXT,
                company_domain  TEXT,
                domain          TEXT,
                linkedin_profile TEXT,
                enrich_person   TEXT,
                final_location  TEXT,
                raw_payload     JSONB,
                created_at      TIMESTAMPTZ DEFAULT NOW()
            );
            CREATE INDEX IF NOT EXISTS idx_campaign
                ON enriched_people(campaign_id);

            -- Migration: add persona_score if missing
            ALTER TABLE enriched_people
                ADD COLUMN IF NOT EXISTS persona_score TEXT;
        """)
