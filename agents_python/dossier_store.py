import psycopg2
import json

PG_CONN_STRING = "postgresql://tender_admin:tender_secret@localhost:5433/tender_intel"


def init_dossier_table():
    conn = psycopg2.connect(PG_CONN_STRING)
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS tender_dossiers (
                id SERIAL PRIMARY KEY,
                link TEXT UNIQUE,
                dossier JSONB,
                saved_at TIMESTAMP DEFAULT NOW()
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS flagged_reviews (
                id SERIAL PRIMARY KEY,
                tender_link TEXT,
                field_name TEXT,
                claimed_value TEXT,
                evidence_snippet TEXT,
                status TEXT DEFAULT 'pending',
                flagged_at TIMESTAMP DEFAULT NOW(),
                reviewed_at TIMESTAMP
            )
        """)
    conn.commit()
    conn.close()


def save_dossier_json(dossier: dict):
    """Stores the clean, structured dossier as JSON — the single source of truth."""
    link = dossier.get("link") or dossier.get("sourceUrl")
    if not link:
        print(f"Skipping dossier save — no link for: {dossier.get('title')}")
        return
    conn = psycopg2.connect(PG_CONN_STRING)
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO tender_dossiers (link, dossier)
            VALUES (%s, %s)
            ON CONFLICT (link) DO UPDATE SET dossier = EXCLUDED.dossier, saved_at = NOW()
        """, (link, json.dumps(dossier)))
    conn.commit()
    conn.close()


def save_flagged_review(tender_link: str, field_name: str, claimed_value: str, evidence_snippet: str | None):
    """Records a verifier-contradicted field for human review. Never auto-corrects."""
    conn = psycopg2.connect(PG_CONN_STRING)
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO flagged_reviews (tender_link, field_name, claimed_value, evidence_snippet)
            VALUES (%s, %s, %s, %s)
        """, (tender_link, field_name, claimed_value, evidence_snippet))
    conn.commit()
    conn.close()


def get_all_dossiers():
    """For re-embedding without touching the LLM again."""
    conn = psycopg2.connect(PG_CONN_STRING)
    with conn.cursor() as cur:
        cur.execute("SELECT dossier FROM tender_dossiers")
        rows = [r[0] for r in cur.fetchall()]
    conn.close()
    return rows