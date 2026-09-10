import psycopg2
import requests
import time

PG_CONN_STRING = "postgresql://tender_admin:tender_secret@localhost:5433/tender_intel"

conn = psycopg2.connect(PG_CONN_STRING)
cur = conn.cursor()

# Get links of failed tenders
cur.execute("SELECT link FROM raw_tenders")
failed_links = [r[0] for r in cur.fetchall()]
print(f"Found {len(failed_links)} failed tenders to reprocess")

success_count = 0
fail_count = 0

for i, link in enumerate(failed_links):
    cur.execute("""
        SELECT title, link, deadline, city, contracting_authority,
               reference_number, category, raw_content
        FROM raw_tenders WHERE link = %s
    """, (link,))
    row = cur.fetchone()
    if not row:
        print(f"[{i+1}/{len(failed_links)}] No raw_tenders match for {link}")
        continue

    raw_tender = {
        "title": row[0],
        "link": row[1],
        "deadline": row[2],
        "city": row[3],
        "contractingAuthority": row[4],
        "referenceNumber": row[5],
        "category": row[6],
        "raw_content": row[7],
    }

    print(f"[{i+1}/{len(failed_links)}] Reprocessing: {raw_tender['title']}")
    try:
        response = requests.post(
            "http://127.0.0.1:8000/validate-and-store",
            json=raw_tender,
            timeout=180
        )
        print(f"   STATUS: {response.status_code}")
        if response.status_code == 200:
            success_count += 1
        else:
            fail_count += 1
    except Exception as e:
        print(f"   FAILED: {e}")
        fail_count += 1

    time.sleep(2)  # small delay to avoid hammering rate limits

conn.close()
print(f"\nDone. Success: {success_count}, Failed: {fail_count}")