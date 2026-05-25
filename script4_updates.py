import re
import time
import cloudscraper
from bs4 import BeautifulSoup
from firestore_utils import FirestoreClient

firebaseConfig = {
    "projectId": "money-d9517",
    "apiKey": "AIzaSyA8TptV1xahItjFpexfqB1OtEZ71DtaogA"
}

def detect_updates():
    db = FirestoreClient(firebaseConfig["projectId"], firebaseConfig["apiKey"])
    scraper = cloudscraper.create_scraper(
        browser={'browser': 'chrome', 'platform': 'android', 'desktop': False}
    )

    completed_novels = db.query_documents("novels", "status", "EQUAL", "completed")

    if completed_novels is None:
        print("[Updates] Database query failed.")
        return

    if not completed_novels:
        print("[Updates] No completed novels to check.")
        return

    print(f"[Updates] Checking {len(completed_novels)} novels for new chapters.")

    for novel in completed_novels:
        novel_id = novel["_id"]
        url = novel.get("url")
        if not url:
            url = f"https://asurascans.com/comics/{novel_id}"

        print(f"[Updates] Checking: {novel_id}")

        try:
            response = scraper.get(url, timeout=15)
            if response.status_code != 200:
                print(f"  [Error] Failed to fetch {url}: {response.status_code}")
                continue

            soup = BeautifulSoup(response.text, 'html.parser')

            new_chapters_found = 0
            found_urls = {}
            for a in soup.find_all('a', href=True):
                href = a['href']
                if '/chapter/' in href or re.search(r'/chapter/\d+', href):
                    full_url = href if href.startswith('http') else f"https://asurascans.com{href}"
                    if full_url not in found_urls:
                        found_urls[full_url] = True

            for full_url in found_urls.keys():
                match = re.search(r'chapter-(\d+)', full_url)
                if not match:
                    match = re.search(r'/chapter/(\d+)', full_url)
                ch_num = int(match.group(1)) if match else 0

                ch_id = f"chapter_{ch_num}"
                existing_ch = db.get_document(f"novels/{novel_id}/chapters", ch_id)

                if not existing_ch:
                    print(f"  [New] Found new chapter: {ch_id}")
                    ch_data = {
                        "url": full_url,
                        "chapter_number": ch_num,
                        "status": "pending",
                        "created_at": int(time.time())
                    }
                    db.save_document(f"novels/{novel_id}/chapters", ch_id, ch_data)
                    new_chapters_found += 1

            if new_chapters_found > 0:
                print(f"  [Info] Added {new_chapters_found} new chapters. Moving back to metadata_scraped.")
                db.save_document("novels", novel_id, {"status": "metadata_scraped"}, merge=True)
            else:
                print(f"  [Info] No new chapters found.")

            time.sleep(2)

        except Exception as e:
            print(f"  [Error] Failed checking {novel_id}: {e}")

if __name__ == "__main__":
    detect_updates()
