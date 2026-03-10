import pandas as pd
import os

# Configuration
SEED_FILE = "data/seed_profiles.csv"

def normalize_url(url):
    """Clean and normalize Instagram URL."""
    if not url:
        return None
    url = url.split("?")[0].rstrip("/")
    if "/p/" in url or "/reels/" in url or "/explore/" in url:
        return None
    return url

def validate_seeds():
    if not os.path.exists(SEED_FILE):
        print(f"Seed file {SEED_FILE} not found.")
        return

    df = pd.read_csv(SEED_FILE)
    initial_count = len(df)
    
    # Normalize and filter
    df["profile_url"] = df["profile_url"].apply(normalize_url)
    df = df.dropna(subset=["profile_url"])
    df = df.drop_duplicates(subset=["profile_url"])
    
    final_count = len(df)
    df.to_csv(SEED_FILE, index=False)
    
    print(f"Validated {SEED_FILE}: {initial_count} -> {final_count} profiles.")

if __name__ == "__main__":
    if not os.path.exists('data'):
        os.makedirs('data')
    validate_seeds()
