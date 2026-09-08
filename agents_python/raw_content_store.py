import psycopg2

PG_CONN_STRING = "postgresql://tender_admin:tender_secret@localhost:5433/tender_intel"

def init_raw_table():
    conn = psycopg2.connect(PG_CONN_STRING)
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS raw_tenders (
                id SERIAL PRIMARY KEY,
                title TEXT,
                link TEXT UNIQUE,
                deadline TEXT,
                city TEXT,
                contracting_authority TEXT,
                reference_number TEXT,
                category TEXT,
                raw_content TEXT,
                fetched_at TIMESTAMP DEFAULT NOW()
            )
        """)
    conn.commit()
    conn.close()


def save_raw_content(tender: dict, raw_content: str):
    """
    Saves one tender's raw crawled text. Uses the tender's link as the
    unique key (ON CONFLICT DO NOTHING) so re-running the fetch never
    creates duplicates - matches the same dedup logic fetch_tenders.py
    already uses for tenders_metadata.json.
    """
    conn = psycopg2.connect(PG_CONN_STRING)
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO raw_tenders
                    (title, link, deadline, city, contracting_authority, reference_number, category, raw_content)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (link) DO NOTHING
            """, (
                tender.get("title"), tender.get("link"), tender.get("deadline"),
                tender.get("city"), tender.get("contracting_authority"),
                tender.get("reference_number"), tender.get("category"), raw_content
            ))
        conn.commit()
    except Exception as e:
        print(f"Failed to save raw content to Postgres for {tender.get('title')}: {e}")
    finally:
        conn.close()

def get_raw_content_by_title(title: str) -> str:
    """
    Used by the fact-check guardrail in main.py, which only receives the
    AI-processed dossier fields (via Mastra), not the original raw text.
    Title is the shared key available on both sides - not perfectly
    collision-proof, but good enough given titles are long, specific
    tender names in practice.
    """
    conn = psycopg2.connect(PG_CONN_STRING)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT raw_content FROM raw_tenders WHERE title = %s LIMIT 1", (title,))
            row = cur.fetchone()
            return row[0] if row else ""
    except Exception as e:
        print(f"Failed to look up raw content for '{title}': {e}")
        return ""
    finally:
        conn.close()

def save_failed_tender(tender: dict, error: str):
    conn = psycopg2.connect(PG_CONN_STRING)
    try:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS failed_tenders (
                    id SERIAL PRIMARY KEY,
                    title TEXT,
                    link TEXT,
                    error TEXT,
                    failed_at TIMESTAMP DEFAULT NOW()
                )
            """)
            cur.execute("""
                INSERT INTO failed_tenders (title, link, error)
                VALUES (%s, %s, %s)
            """, (tender.get("title"), tender.get("link"), error))
        conn.commit()
    except Exception as e:
        print(f"Failed to log failure: {e}")
    finally:
        conn.close()