import json
import re
import time
from bs4 import BeautifulSoup
import cloudscraper
import requests

# Firebase Web SDK configuration
firebaseConfig = {
    "apiKey": "AIzaSyA8TptV1xahItjFpexfqB1OtEZ71DtaogA",
    "authDomain": "money-d9517.firebaseapp.com",
    "databaseURL": "https://money-d9517-default-rtdb.firebaseio.com",
    "projectId": "money-d9517",
    "storageBucket": "money-d9517.firebasestorage.app",
    "messagingSenderId": "1028474173381",
    "appId": "1:1028474173381:web:6e2925596d3d8a58af7dac"
}


class FirestoreClient:
    """
    A lightweight Firestore client utilizing the native REST API.
    Designed for zero-dependency execution in PyDroid3.
    """
    def __init__(self, project_id):
        self.project_id = project_id
        self.base_url = f"https://firestore.googleapis.com/v1/projects/{project_id}/databases/(default)/documents"

    def _to_firestore_value(self, val):
        """Converts standard Python types into strict Firestore REST formats."""
        if isinstance(val, str):
            return {"stringValue": val}
        elif isinstance(val, bool):
            return {"booleanValue": val}
        elif isinstance(val, (int, float)):
            if isinstance(val, float):
                return {"doubleValue": val}
            return {"integerValue": str(val)}
        elif isinstance(val, list):
            return {"arrayValue": {"values": [self._to_firestore_value(v) for v in val]}}
        elif isinstance(val, dict):
            return {"mapValue": {"fields": {k: self._to_firestore_value(v) for k, v in val.items()}}}
        elif val is None:
            return {"nullValue": None}
        return {"stringValue": str(val)}

    def _to_firestore_doc(self, py_dict):
        return {"fields": {k: self._to_firestore_value(v) for k, v in py_dict.items()}}

    def save_document(self, path, doc_id, data):
        """
        Saves a document to a collection or subcollection path.
        'path' can be a top-level collection (e.g., 'novels')
        or a nested subcollection path (e.g., 'novels/barbarian-quest/chapters').
        """
        url = f"{self.base_url}/{path}/{doc_id}"
        doc_data = self._to_firestore_doc(data)
        try:
            response = requests.patch(url, json=doc_data, timeout=10)
            if response.status_code in [200, 201]:
                print(f"[Firestore] Successfully saved: {path}/{doc_id}")
                return True
            else:
                print(f"[Firestore Error] Failed to write {path}/{doc_id}: {response.text}")
                return False
        except Exception as e:
            print(f"[Firestore Error] Request failed: {e}")
            return False


def scrape_and_save_asura_data(url, max_chapters_to_scrape=None):
    """
    Scrapes metadata + chapter images and saves them directly to Firestore.
    :param url: Target comic URL.
    :param max_chapters_to_scrape: Set to None (default) to process and upload all chapters.
    """
    print("[System] Initializing native Android cloud session...")
    
    # Initialize the Firestore Client
    db = FirestoreClient(firebaseConfig["projectId"])
    
    # Extract unique novel slug ID from URL (e.g. 'barbarian-quest')
    novel_id = url.rstrip('/').split('/')[-1]
    
    scraper = cloudscraper.create_scraper(
        browser={
            'browser': 'chrome',
            'platform': 'android',
            'desktop': False
        }
    )
    
    try:
        print(f"[System] Requesting main target URL: {url}")
        response = scraper.get(url, timeout=15)
        response.encoding = 'utf-8'
        
        if response.status_code != 200:
            print(f"[Error] Main request blocked: status code {response.status_code}")
            return
            
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # --- PHASE 1: PARSE STRUCTURED SCHEMA DATA (JSON-LD) ---
        schema_meta = {}
        ld_json_scripts = soup.find_all('script', type='application/ld+json')
        
        for script in ld_json_scripts:
            if script.string:
                try:
                    data = json.loads(script.string)
                    schema_type = data.get('@type')
                    if schema_type in ['ComicSeries', 'Article']:
                        for key, val in data.items():
                            if val:
                                schema_meta[key] = val
                except json.JSONDecodeError:
                    continue
        
        print("\n" + "="*40)
        print("        EXTRACTING METADATA")
        print("="*40)
        
        # 1. Title
        title = schema_meta.get('name') or schema_meta.get('headline') or "Unknown Title"
        
        # 2. Alternative Titles
        alt_titles = ""
        alt_header = soup.find(lambda tag: tag.name in ['h1', 'h2', 'h3', 'h4', 'div', 'p', 'span'] 
                               and tag.text and 'alternative' in tag.text.strip().lower())
        if alt_header:
            next_node = alt_header.find_next()
            if next_node:
                text = next_node.text.strip()
                if text and len(text) > 2 and "description" not in text.lower():
                    alt_titles = re.sub(r'\s+', ' ', text).strip()
        
        # 3. Cover Image
        cover_url = "Not Found"
        image_val = schema_meta.get('image')
        if image_val:
            if isinstance(image_val, dict):
                cover_url = image_val.get('url', 'Not Found')
            elif isinstance(image_val, str):
                cover_url = image_val
        else:
            og_image = soup.find('meta', property='og:image')
            if og_image and og_image.get('content'):
                cover_url = og_image['content']
                
        # 4. Genres
        genres = []
        genre_val = schema_meta.get('genre')
        if genre_val:
            if isinstance(genre_val, list):
                genres = genre_val
            elif isinstance(genre_val, str):
                genres = [g.strip() for g in genre_val.split(',') if g.strip()]
        if not genres:
            KNOWN_GENRES = {
                "action", "adventure", "comedy", "drama", "fantasy", "historical", "horror",
                "mystery", "romance", "sci-fi", "slice of life", "sports", "supernatural",
                "tragedy", "isekai", "regression", "revenge", "martial arts", "murim",
                "shounen", "shoujo", "seinen", "josei", "mecha", "psychological", "thriller",
                "violence", "gore", "magic", "monster", "monsters", "demons", "survival"
            }
            for tag in soup.find_all(['a', 'button', 'span']):
                txt = tag.text.strip().lower()
                if txt in KNOWN_GENRES:
                    genres.append(tag.text.strip())
            genres = list(set(genres))
            
        # 5. Synopsis / Description
        description = schema_meta.get('description') or ""
        if description:
            search_prefix = description[:35].strip()
            if len(search_prefix) >= 15:
                candidates = []
                for tag_name in ['p', 'div', 'span']:
                    for tag in soup.find_all(tag_name):
                        tag_text_clean = re.sub(r'\s+', ' ', tag.text).strip()
                        if search_prefix in tag_text_clean:
                            for term in ["Show more", "Show less", "See more", "Rating", "Chapters"]:
                                if term in tag_text_clean:
                                    tag_text_clean = tag_text_clean.split(term)[0].strip()
                            if (len(tag_text_clean) >= len(description) and 
                                    not (tag_text_clean.endswith('...') or tag_text_clean.endswith('\u2026')) and 
                                    len(tag_text_clean) < 2000):
                                candidates.append(tag_text_clean)
                if candidates:
                    candidates = sorted(candidates, key=len)
                    description = candidates[0]

        # Structure Metadata for Firestore
        novel_data = {
            "title": title,
            "alternative_titles": alt_titles,
            "cover_url": cover_url,
            "genres": genres,
            "description": description,
            "last_updated": int(time.time())
        }
        
        # Save Top-Level Metadata to 'novels' collection
        db.save_document("novels", novel_id, novel_data)
        
        # --- PHASE 2: EXTRACT CHAPTER LINKS ---
        unique_chapters = {}
        for a in soup.find_all('a', href=True):
            href = a['href']
            if '/chapter/' in href or re.search(r'/chapter/\d+', href):
                full_url = href if href.startswith('http') else f"https://asurascans.com{href}"
                slug_parts = href.rstrip('/').split('/')
                ch_slug = slug_parts[-1]
                label = f"Chapter {ch_slug.replace('-', ' ').title()}"
                if full_url not in unique_chapters:
                    unique_chapters[full_url] = label

        if unique_chapters:
            def get_chapter_number(item):
                url, _ = item
                match = re.search(r'/chapter/(\d+)', url)
                return int(match.group(1)) if match else 0
            
            # Sort from Chapter 1 upwards
            sorted_chapters = sorted(unique_chapters.items(), key=get_chapter_number, reverse=False)
            total_chapters = len(sorted_chapters)
            print(f"\n[System] Found {total_chapters} chapters total.")
            
            # Apply chapter limitations if set
            if max_chapters_to_scrape:
                print(f"[System] Safety limit active. Processing first {max_chapters_to_scrape} chapters.")
                sorted_chapters = sorted_chapters[:max_chapters_to_scrape]
            
            # --- PHASE 3: SCRAPE CHAPTER IMAGES & UPLOAD TO NESTED FIRESTORE SUBCOLLECTION ---
            print("\n" + "="*40)
            print("        SCRAPING & UPLOADING PAGES")
            print("="*40)
            
            for ch_url, label in sorted_chapters:
                ch_num = get_chapter_number((ch_url, label))
                print(f"\n[Scraper] Requesting: {label} -> {ch_url}")
                
                try:
                    ch_res = scraper.get(ch_url, timeout=15)
                    ch_res.encoding = 'utf-8'
                    
                    if ch_res.status_code != 200:
                        print(f"  [Warning] Failed to fetch {label} (HTTP {ch_res.status_code}). Skipping...")
                        continue
                        
                    ch_soup = BeautifulSoup(ch_res.text, 'html.parser')
                    
                    # Extract page image urls from the chapter reader
                    img_srcs = []
                    for img in ch_soup.find_all('img'):
                        src = img.get('src') or img.get('data-src') or img.get('data-lazy-src')
                        if src:
                            src = src.strip()
                            if src.startswith('//'):
                                src = f"https:{src}"
                            elif src.startswith('/'):
                                src = f"https://asurascans.com{src}"
                                
                            # Filter out noisy UI elements
                            if any(x in src.lower() for x in ["logo", "avatar", "icon", "banner", "loader", "placeholder", "discord"]):
                                continue
                                
                            # Capture page layout panels
                            if "cdn" in src.lower() or "asura-images" in src.lower() or re.search(r'\.(webp|jpg|jpeg|png)(\?|$)', src, re.IGNORECASE):
                                if src not in img_srcs:
                                    img_srcs.append(src)
                    
                    if img_srcs:
                        # Structure pages as a map where keys correspond to "1", "2", "3" (Page numbers)
                        pages_map = {str(i + 1): img_url for i, img_url in enumerate(img_srcs)}
                        
                        chapter_doc_data = {
                            "chapter_label": label,
                            "chapter_number": ch_num,
                            "pages": pages_map,
                            "total_pages": len(img_srcs)
                        }
                        
                        # Define subcollection path: 'novels/{novel_id}/chapters'
                        subcollection_path = f"novels/{novel_id}/chapters"
                        chapter_doc_id = f"chapter_{ch_num}"
                        
                        # Save the document inside the subcollection
                        db.save_document(subcollection_path, chapter_doc_id, chapter_doc_data)
                        print(f"  [Success] Saved {len(img_srcs)} pages to {subcollection_path}/{chapter_doc_id}")
                    else:
                        print(f"  [Warning] No reading images could be parsed inside {label}.")
                        
                    # 1.5-second sleep delay to protect your IP from being flagged/banned by Cloudflare
                    time.sleep(1.5)
                    
                except Exception as ch_err:
                    print(f"  [Error] Failed parsing {label}: {ch_err}")
                    
            print("\n[System] Database sync completed.")
        else:
            print("[Error] No chapter links could be parsed from the layout.")
            
    except Exception as e:
        print(f"\n[Execution Failure] Script stopped by exception: {e}")


if __name__ == "__main__":
    # Target URL
    target_url = "https://asurascans.com/comics/barbarian-quest"
    
    # Run the scraping/database pipeline.
    # 'max_chapters_to_scrape' is set to None to scrape and upload all chapters chronologically.
    scrape_and_save_asura_data(target_url, max_chapters_to_scrape=None)