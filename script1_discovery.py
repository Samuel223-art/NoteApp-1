import time
import cloudscraper
from bs4 import BeautifulSoup
from firestore_utils import FirestoreClient

firebaseConfig = {
    "projectId": "money-d9517",
    "apiKey": "AIzaSyA8TptV1xahItjFpexfqB1OtEZ71DtaogA"
}

def discover_novels():
    db = FirestoreClient(firebaseConfig["projectId"], firebaseConfig["apiKey"])
    scraper = cloudscraper.create_scraper(
        browser={'browser': 'chrome', 'platform': 'android', 'desktop': False}
    )

    base_url = "https://asurascans.com"
    browse_url = f"{base_url}/browse"

    print(f"[Discovery] Fetching {browse_url}...")
    try:
        response = scraper.get(browse_url, timeout=15)
        if response.status_code != 200:
            print(f"[Error] Failed to fetch browse page: {response.status_code}")
            return

        soup = BeautifulSoup(response.text, 'html.parser')

        novel_links = []
        for a in soup.find_all('a', href=True):
            href = a['href']
            if '/comics/' in href:
                if href.startswith('/'):
                    href = f"{base_url}{href}"
                if href not in novel_links:
                    novel_links.append(href)

        print(f"[Discovery] Found {len(novel_links)} novel links on page.")

        new_found = 0
        for link in novel_links:
            if new_found >= 10:
                break

            novel_id = link.rstrip('/').split('/')[-1]
            if not novel_id or novel_id == 'comics': continue

            existing = db.get_document("novels", novel_id)
            if not existing:
                print(f"[Discovery] New novel found: {novel_id}")
                data = {
                    "url": link,
                    "status": "discovered",
                    "created_at": int(time.time())
                }
                if db.save_document("novels", novel_id, data):
                    new_found += 1
            else:
                pass

        print(f"[Discovery] Finished. Added {new_found} new novels.")

    except Exception as e:
        print(f"[Discovery Error] {e}")

if __name__ == "__main__":
    discover_novels()
