import re
import time
import cloudscraper
import requests
from bs4 import BeautifulSoup
from firestore_utils import FirestoreClient

firebaseConfig = {
    "projectId": "money-d9517",
    "apiKey": "AIzaSyA8TptV1xahItjFpexfqB1OtEZ71DtaogA"
}

def scrape_chapter_images():
    db = FirestoreClient(firebaseConfig["projectId"], firebaseConfig["apiKey"])
    scraper = cloudscraper.create_scraper(
        browser={'browser': 'chrome', 'platform': 'android', 'desktop': False}
    )

    active_novels = db.query_documents("novels", "status", "EQUAL", "metadata_scraped")

    if active_novels is None:
        print("[Chapters] Database query failed. Aborting.")
        return

    if not active_novels:
        print("[Chapters] No novels ready for chapter scraping.")
        return

    for novel in active_novels:
        novel_id = novel["_id"]
        print(f"[Chapters] Processing Novel: {novel_id}")

        chapters = db.query_documents(f"novels/{novel_id}/chapters", "status", "EQUAL", "pending")

        if chapters is None:
            print(f"  [Error] Failed to query chapters for {novel_id}. Skipping.")
            continue

        if not chapters:
            print(f"  [Info] All chapters for {novel_id} are already processed.")
            db.save_document("novels", novel_id, {"status": "completed"}, merge=True)
            continue

        print(f"  [Chapters] Found {len(chapters)} pending chapters.")

        processed_successfully = 0
        for ch in chapters:
            ch_id = ch["_id"]
            ch_url = ch["url"]
            print(f"    [Scraping] {ch_id} -> {ch_url}")

            try:
                ch_res = scraper.get(ch_url, timeout=15)
                if ch_res.status_code != 200:
                    print(f"      [Warning] Failed HTTP {ch_res.status_code}")
                    continue

                ch_soup = BeautifulSoup(ch_res.text, 'html.parser')
                img_srcs = []
                for img in ch_soup.find_all('img'):
                    src = img.get('src') or img.get('data-src') or img.get('data-lazy-src')
                    if src:
                        src = src.strip()
                        if any(x in src.lower() for x in ["logo", "avatar", "icon", "banner", "loader", "placeholder", "discord"]):
                            continue
                        if "cdn" in src.lower() or "asura-images" in src.lower() or re.search(r'\.(webp|jpg|jpeg|png)(\?|$)', src, re.IGNORECASE):
                            if src not in img_srcs:
                                img_srcs.append(src)

                if img_srcs:
                    pages_map = {str(i + 1): img_url for i, img_url in enumerate(img_srcs)}
                    ch_update = {
                        "pages": pages_map,
                        "total_pages": len(img_srcs),
                        "status": "completed",
                        "updated_at": int(time.time())
                    }
                    if db.save_document(f"novels/{novel_id}/chapters", ch_id, ch_update, merge=True):
                        processed_successfully += 1
                        print(f"      [Success] Saved {len(img_srcs)} pages.")
                else:
                    print(f"      [Warning] No images found.")

                time.sleep(1.5)
            except Exception as e:
                print(f"      [Error] {e}")

        # Only mark novel as completed if we processed all pending chapters
        # Re-query to be sure
        remaining = db.query_documents(f"novels/{novel_id}/chapters", "status", "EQUAL", "pending")
        if remaining is not None and len(remaining) == 0:
            db.save_document("novels", novel_id, {"status": "completed"}, merge=True)
            print(f"  [Finished] Novel {novel_id} marked as completed.")

if __name__ == "__main__":
    scrape_chapter_images()
