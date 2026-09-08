import os
import re
import time
import json
import asyncio
import requests
import feedparser
import pdfplumber
import io
from crawl4ai import AsyncWebCrawler
from bs4 import BeautifulSoup
from pydantic import BaseModel
from urllib.parse import urlparse, urljoin, urlsplit, urlunsplit
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By

from raw_content_store import init_raw_table, save_raw_content, save_failed_tender

JOB_POSTING_MARKER = "(m/w/d)"


CRWL_TIMEOUT_SECONDS = 90

SEARCH_TERMS = ["wahlunterlagen", "scandienstleistungen", "digitalisierung"]
BASE_URL = "https://www.service.bund.de/Content/DE/Ausschreibungen/Suche/Formular.html"
RSS_SEARCH_PARAMS = {
    "nn": "4641482",           # site-internal ID for this search 
    "type": "0",               
    "resultsPerPage": "100",
    "sortOrder": "dateOfIssue_dt desc",
    "jobsrss": "true",         
}

HEADERS = {"User-Agent": "TenderBot/1.0"}
def fetch_rss_entries(search_terms: list[str] = SEARCH_TERMS):
    all_entries = []
    seen_links = set()
    for term in search_terms:
        params = {**RSS_SEARCH_PARAMS, "templateQueryString": term}
        r = requests.get(BASE_URL, headers=HEADERS, params=params, timeout=10)
        r.raise_for_status()
        feed = feedparser.parse(r.text)
        for e in feed.entries:
            if e.link not in seen_links:
                all_entries.append({"title": e.title, "link": e.link, "category": term})
                seen_links.add(e.link)
    return all_entries

def extract_deadline_and_announcement(html: str):
    soup = BeautifulSoup(html, "html.parser")
    deadline = "—"
    dt = soup.find("dt", string=lambda t: t and "Angebotsfrist" in t)
    if dt:
        dd = dt.find_next_sibling("dd")
        if dd:
            deadline = dd.get_text(strip=True)

    a = soup.find("a", string=lambda t: t and "Bekanntmachung" in t)
    href = None
    if a:
        href = a.get("href")
        if href:
            href = " ".join(href.split())
            if not href.startswith("http"):
                href = "https://www.service.bund.de" + href

    return deadline, href if href else None

def extract_city(html: str) -> str | None:
    soup = BeautifulSoup(html, "html.parser")
    dt = soup.find("dt", string=lambda t: t and "Erfüllungsort" in t)
    if dt:
        dd = dt.find_next_sibling("dd")
        if dd:
            lines = [l.strip() for l in dd.get_text(separator="\n").split("\n") if l.strip()]
            for line in lines:
                if line and not line.isdigit() and "Karte" not in line and "CPV" not in line:
                    return line
    return None


def extract_contracting_authority(html: str) -> str | None:
    soup = BeautifulSoup(html, "html.parser")
    dt = soup.find("dt", string=lambda t: t and "Vergabestelle" in t)
    if dt:
        dd = dt.find_next_sibling("dd")
        if dd:
            return dd.get_text(strip=True)
    return None


def extract_reference_number(html: str) -> str | None:
    soup = BeautifulSoup(html, "html.parser")
    dt = soup.find("dt", string=lambda t: t and ("Vergabenummer" in t or "Aktenzeichen" in t))
    if dt:
        dd = dt.find_next_sibling("dd")
        if dd:
            return dd.get_text(strip=True)
    return None


def extract_from_crawled_markdown(markdown_text: str) -> dict:
    result = {"contracting_authority": None, "reference_number": None, "cpv_code": None}

    auth_match = re.search(
        r"####\s*Auftraggeber\s*/\s*Ausschreibende Stelle\s*\n+(.+?)(?=\n####|\n\n|\Z)",
        markdown_text, re.IGNORECASE | re.DOTALL
    )
    if auth_match:
        result["contracting_authority"] = auth_match.group(1).strip()

    ref_match = re.search(
        r"####\s*Ausschreibungs-ID\s*\n+(.+?)(?=\n####|\n\n|\Z)",
        markdown_text, re.IGNORECASE | re.DOTALL
    )
    if ref_match:
        result["reference_number"] = ref_match.group(1).strip()

    cpv_match = re.search(r"\b(\d{8}-\d)\b", markdown_text)
    if cpv_match:
        result["cpv_code"] = cpv_match.group(1)

    return result


def extract_all_tab_urls(driver, base_url):
    try:
        driver.get(base_url)
    except Exception as e:
        print(f"  page load timed out/failed: {base_url} ({e})")
        return []
    time.sleep(3)

    base = urlparse(base_url)
    root = f"{base.scheme}://{base.netloc}"
    tab_urls = set()

    for link in driver.find_elements(By.TAG_NAME, "a"):
        href = link.get_attribute("href")
        if (href and "/VMPSatellite/public/company/project/" in href and "/de/" in href
                and "/communication" not in href and "/documents" not in href):
            clean = re.sub(r";jsessionid=[^?#]*", "", href)
            full_url = urljoin(root, clean)
            parts = urlsplit(full_url)
            normalized = urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))
            tab_urls.add(normalized)

    return sorted(tab_urls)

def extract_pdf_text(url: str) -> str:
    try:
        resp = requests.get(url, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        text_chunks = []
        with pdfplumber.open(io.BytesIO(resp.content)) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text() or ""
                text_chunks.append(page_text)
        return "\n".join(text_chunks)
    except Exception as e:
        print(f"Failed to read PDF {url}: {e}")
        return ""


async def run_crwl_async(crawler, url):
    if url.lower().endswith(".pdf"):
        return await asyncio.to_thread(extract_pdf_text, url)


    print(f"  crawling: {url}")
    try:
        result = await asyncio.wait_for(crawler.arun(url=url), timeout=CRWL_TIMEOUT_SECONDS)
        if not getattr(result, "success", True):
            print(f"crwl failed on {url}: {getattr(result, 'error_message', 'unknown error')}")
            return ""
        return getattr(result, "markdown", "") or ""
    except asyncio.TimeoutError:
        print(f"Timed out after {CRWL_TIMEOUT_SECONDS}s crawling: {url}")
        return ""
    except Exception as e:
        print(f"crwl failed on {url}: {e}")
        return ""

def clean_all_markdown_files(directory="."):
    noisy_patterns = [
        r'^\s*[*\-_=]{3,}\s*$',
        r'\[.*\]\(javascript:.*\)',
        r'\[.*\]\(#.*\)',
        r'\[.*\]\(\)',
        r'^Bitte warten.*',
        r'^\s*\[\s*\]\s*$',
    ]
    noisy_keywords = [
        "impressum", "datenschutz", "barrierefreiheit", "systemzeit",
        "administration intelligence", "cosinex", "d-nrw", "vo:",
        "vmp", "zurück", "anmelden", "teilnehmen", "seite drucken",
        "javascript", "bitte warten", "mandantennummer"
    ]

    def is_noisy(line):
        l = line.lower()
        return any(k in l for k in noisy_keywords) or any(re.search(p, line) for p in noisy_patterns)

    for fname in os.listdir(directory):
        if fname.endswith(".md"):
            with open(fname, "r", encoding="utf-8") as f:
                lines = f.readlines()
            cleaned = [line for line in lines if not is_noisy(line)]
            with open(fname, "w", encoding="utf-8") as f:
                f.writelines(cleaned)


async def fetch_and_process():
    existing = []
    if os.path.exists("tenders_metadata.json"):
        with open("tenders_metadata.json", "r", encoding="utf-8") as f:
            existing = json.load(f)

    init_raw_table()  # creates raw_tenders in Postgres if it doesn't exist yet

    existing_links = {t["link"] for t in existing}
    fetched = fetch_rss_entries()
    newly_added = []

    def save_progress():
        with open("tenders_metadata.json", "w", encoding="utf-8") as f:
            json.dump(existing, f, indent=2, ensure_ascii=False)
        with open("tenders_index.json", "w", encoding="utf-8") as f:
            json.dump(existing, f, indent=2, ensure_ascii=False)

    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--no-sandbox")
    driver = webdriver.Chrome(options=options)
    driver.set_page_load_timeout(30)
    async with AsyncWebCrawler() as crawler:
        try:
            for entry in fetched:
                if entry["link"] in existing_links:
                    continue

                if JOB_POSTING_MARKER.lower() in entry["title"].lower():
                    print(f"Skipping (job posting): {entry['title']}")
                    continue

                try:
                    html = requests.get(entry["link"], headers=HEADERS, timeout=10).text
                    deadline, ann_url = extract_deadline_and_announcement(html)
                    city = extract_city(html)
                    contracting_authority = extract_contracting_authority(html)
                    reference_number = extract_reference_number(html)

                    tender = Tender(
                        title=entry["title"],
                        link=entry["link"],
                        deadline=deadline,
                        announcement_url=ann_url,
                        city=city,
                        contracting_authority=contracting_authority,
                        reference_number=reference_number,
                        category=entry["category"]
                    ).model_dump()

                    if ann_url:
                        tab_links = extract_all_tab_urls(driver, ann_url)
                        if ann_url not in tab_links:
                            tab_links.insert(0, ann_url)

                        contents = await asyncio.gather(
                            *(run_crwl_async(crawler, url) for url in tab_links)
                        )

                        full_md = ""
                        for url, content in zip(tab_links, contents):
                            if content:
                                full_md += f"\n\n# Content from {url}\n\n{content}\n{'=' * 80}\n"

                        safe_title = re.sub(r"[^\w\s-]", "", entry["title"]).strip().replace(" ", "_")[:60]
                        md_filename = f"{safe_title}.md"
                        with open(md_filename, "w", encoding="utf-8") as f:
                            f.write(full_md)
                        tender["md_file"] = md_filename

                        save_raw_content(tender, full_md)

                        found = extract_from_crawled_markdown(full_md)
                        if not tender.get("contracting_authority") and found["contracting_authority"]:
                            tender["contracting_authority"] = found["contracting_authority"]
                        if not tender.get("reference_number") and found["reference_number"]:
                            tender["reference_number"] = found["reference_number"]

                    existing.append(tender)
                    newly_added.append(tender)
                    save_progress()

                except Exception as e:
                    print(f"Error processing tender: {e}")
                    save_progress()
        finally:
            driver.quit()

    clean_all_markdown_files()
    return newly_added

MASTRA_ENRICH_URL = "http://localhost:3000/enrich-and-store"

def dispatch_to_mastra(newly_added: list[dict]):
    """
    Replaces the old build_vector_store() step. Instead of building a
    separate Chroma index, each new tender's deterministic fields + its
    collected markdown content are handed to the Mastra scout agent,
    which only fills in the judgment-based fields (sector, keywords,
    summary, valueScore, confidenceScore) — never re-deriving title,
    deadline, city, contracting_authority, or reference_number, which
    are already reliable from BeautifulSoup above.
    """
    for tender in newly_added:
        md_file = tender.get("md_file")
        markdown_text = ""
        if md_file and os.path.exists(md_file):
            with open(md_file, encoding="utf-8") as f:
                markdown_text = f.read()

        payload = {**tender, "markdown": markdown_text}

        try:
            resp = requests.post(MASTRA_ENRICH_URL, json=payload, timeout=120)
            resp.raise_for_status()
            print(f"Dispatched to Mastra: {tender['title']} -> {resp.json().get('status')}")

            if md_file and os.path.exists(md_file):
                os.remove(md_file)

        except Exception as e:
            print(f"Failed to dispatch {tender['title']} to Mastra: {e}")
            save_failed_tender(tender, str(e))

class Tender(BaseModel):
    title: str
    link: str
    deadline: str
    announcement_url: str | None
    city: str | None = None
    contracting_authority: str | None = None
    reference_number: str | None = None
    md_file: str | None = None
    category: str | None = None

if __name__ == "__main__":
    newly_added = asyncio.run(fetch_and_process())
    dispatch_to_mastra(newly_added)