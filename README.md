# Distributed Novel Scraper

This system splits the scraping process into 4 stages to allow running on multiple GitHub accounts via GitHub Actions, avoiding resource limits.

## Project Structure

- `script1_discovery.py`: Finds new novels and adds them to Firestore.
- `script2_metadata.py`: Scrapes novel details and chapter links.
- `script3_chapters.py`: Scrapes image URLs for each chapter.
- `script4_updates.py`: Monitors completed novels for new chapter releases.
- `firestore_utils.py`: Shared utility for Firestore database communication.
- `.github/workflows/`: Contains the automation files for GitHub Actions.

## Setup Instructions

### 1. Prepare your GitHub Repositories
Since you want to use **3 different GitHub accounts**, follow this suggested split:

*   **Account 1 (The Scout):**
    - Upload `script1_discovery.py`, `script4_updates.py`, and `firestore_utils.py`.
    - Keep only `discovery.yml` and `updates.yml` in the `.github/workflows/` folder.
*   **Account 2 (The Librarian):**
    - Upload `script2_metadata.py` and `firestore_utils.py`.
    - Keep only `metadata.yml` in the `.github/workflows/` folder.
*   **Account 3 (The Worker):**
    - Upload `script3_chapters.py` and `firestore_utils.py`.
    - Keep only `chapters.yml` in the `.github/workflows/` folder.

### 2. Enable GitHub Actions
In each GitHub repository:
1. Go to the **Settings** tab.
2. Click on **Actions** -> **General** on the left sidebar.
3. Ensure "Allow all actions and reusable workflows" is selected.
4. Scroll down to "Workflow permissions" and ensure "Read and write permissions" is selected (required if the script needs to commit changes, though these scripts mostly talk to Firestore).

### 3. Run the Scripts
- The scripts are set to run automatically every **30 minutes**.
- To start them manually:
    1. Go to the **Actions** tab in your repository.
    2. Select the workflow name (e.g., "Novel Discovery") on the left.
    3. Click the **Run workflow** dropdown button and click **Run workflow**.

## Notes
- **Firebase Credentials:** All credentials are already hardcoded in the scripts as requested.
- **Dependencies:** The GitHub Actions will automatically install `cloudscraper`, `beautifulsoup4`, and `requests` every time they run.
