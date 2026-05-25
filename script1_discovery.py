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
    new_found_total = 0
    page_num = 1
    
    print("[Discovery] Starting paginated discovery...")
    
    while new_found_total < 10:
        browse_url = f"{base_url}/browse?page={page_num}"
        print(f"[Discovery] Fetching Page {page_num}: {browse_url}...")
        
        try:
            response = scraper.get(browse_url, timeout=15)
            if response.status_code != 200:
                print(f"[Error] Failed to fetch page {page_num}: {response.status_code}")
                break
                
            soup = BeautifulSoup(response.text, 'html.parser')
            
            novel_links = []
            for a in soup.find_all('a', href=True):
                href = a['href']
                if '/comics/' in href:
                    if href.startswith('/'):
                        href = f"{base_url}{href}"
                    if href not in novel_links:
                        novel_links.append(href)
            
            if not novel_links:
                print(f"[Discovery] No novels found on page {page_num}. Stopping.")
                break
            
            print(f"[Discovery] Found {len(novel_links)} novel links on page {page_num}.")
            
            page_already_seen = True
            for link in novel_links:
                if new_found_total >= 10:
                    break
                    
                novel_id = link.rstrip('/').split('/')[-1]
                if not novel_id or novel_id == 'comics': continue
                
                # Check if exists
                existing = db.get_document("novels", novel_id)
                if not existing:
                    print(f"  [New] Novel found: {novel_id}")
                    data = {
                        "url": link,
                        "status": "discovered",
                        "created_at": int(time.time())
                    }
                    if db.save_document("novels", novel_id, data):
                        new_found_total += 1
                        page_already_seen = False
                else:
                    # Novel already exists, so this link was seen before
                    pass
            
            # If every novel on this page was already in our database, 
            # we've likely caught up to where we left off.
            if page_already_seen:
                print(f"[Discovery] All novels on page {page_num} are already in database. Stopping.")
                break
                
            page_num += 1
            time.sleep(1) # Small delay between pages
            
        except Exception as e:
            print(f"[Discovery Error] {e}")
            break
                
    print(f"[Discovery] Finished. Added {new_found_total} new novels total.")

if __name__ == "__main__":
    discover_novels()
    
