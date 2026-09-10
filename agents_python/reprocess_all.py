import psycopg2
import requests
import time

PG_CONN_STRING = "postgresql://tender_admin:tender_secret@localhost:5433/tender_intel"

conn = psycopg2.connect(PG_CONN_STRING)
cur = conn.cursor()
cur.execute("SELECT link FROM raw_tenders")
links = [r[0] for r in cur.fetchall()]
conn.close()

print(f"Found {len(links)} tenders to process")

success_count = 0
fail_count = 0

conn = psycopg2.connect(PG_CONN_STRING)
cur = conn.cursor()

for i, link in enumerate(links):
    cur.execute("""
        SELECT title, link, deadline, city, contracting_authority,
               reference_number, category, raw_content
        FROM raw_tenders WHERE link = %s
    """, (link,))
    row = cur.fetchone()
    if not row:
        continue

    raw_tender = {
        "title": row[0],
        "link": row[1],
        "deadline": row[2],
        "city": row[3],
        "contracting_authority": row[4],
        "reference_number": row[5],
        "category": row[6],
        "markdown": row[7],
    }

    print(f"[{i+1}/{len(links)}] Processing: {raw_tender['title']}")
    try:
        response = requests.post(
            "http://localhost:3000/enrich-and-store",
            json=raw_tender,
            timeout=180
        )
        print(f"   STATUS: {response.status_code}")
        if response.status_code == 200:
            success_count += 1
        else:
            print(f"   BODY: {response.text[:300]}")
            fail_count += 1
    except Exception as e:
        print(f"   FAILED: {e}")
        fail_count += 1

    time.sleep(3)

conn.close()
print(f"\nDone. Success: {success_count}, Failed: {fail_count}")