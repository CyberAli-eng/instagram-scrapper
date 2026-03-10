import asyncio
import os
import pandas as pd
import random
import sys

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from playwright.async_api import async_playwright
from utils.auth import get_logged_in_context

# Configuration
SEED_FILE = "data/influencers.csv"
OUTPUT_FILE = "data/seed_profiles.csv" # Feed back into discovery
EXPANDED_FILE = "data/expanded.txt" # Track who we already expanded from
MIN_FOLLOWERS_THRESHOLD = 1000
MAX_FOLLOWERS_TO_SCRAPE = 2000

async def scrape_followers(page, username):
    """Navigates to an influencer's followers list and extracts potential leads."""
    print(f"Expanding from influencer: {username}", flush=True)
    discovered_profiles = set()
    
    try:
        # Navigate to profile first
        print(f"  Navigating to profile: {username}", flush=True)
        await page.goto(f"https://www.instagram.com/{username}/", timeout=60000)
        await asyncio.sleep(random.uniform(1, 2))
        
        # Click on "followers" link specifically
        try:
            followers_btn = await page.wait_for_selector(f'a[href="/{username}/followers/"]', timeout=10000)
            await followers_btn.click()
            print("  Followers button clicked.", flush=True)
        except:
            print("  Followers button not found via selector, navigating directly...", flush=True)
            await page.goto(f"https://www.instagram.com/{username}/followers/", timeout=60000)
        
        # Wait for the modal or the page to load the list
        await asyncio.sleep(5)
        
        # Aggressive modal discovery: find any element that is scrollable
        try:
            modal_handle = await page.evaluate_handle('''() => {
                const elements = document.querySelectorAll('div[style*="overflow-y: auto"], div._aano, div[role="dialog"]');
                for (const el of elements) {
                    if (el.scrollHeight > el.clientHeight) return el;
                }
                // Fallback: search all divs
                const allDivs = document.querySelectorAll('div');
                let best = null;
                let maxScroll = 0;
                for (const div of allDivs) {
                    if (div.scrollHeight > div.clientHeight && div.scrollHeight > maxScroll) {
                        maxScroll = div.scrollHeight;
                        best = div;
                    }
                }
                return best;
            }''')
            if modal_handle.as_element():
                print("  Scrollable modal handle discovered.", flush=True)
                modal = modal_handle.as_element()
            else:
                modal = None
        except:
            modal = None

        last_count = 0
        stall_streak = 0
        for i in range(40): # Deeper scrolls
            if modal:
                await modal.focus()
            
            # Find all profile links and scroll the last one into view
            await page.evaluate('''() => {
                const anchors = Array.from(document.querySelectorAll('a[href^="/"]')).filter(a => {
                    const href = a.getAttribute('href');
                    return href.length > 2 && !href.includes('/p/') && !href.includes('/explore/') && !href.includes('/reels/');
                });
                if (anchors.length > 0) {
                    anchors[anchors.length - 1].scrollIntoView();
                }
            }''')
            
            # Fallback PageDown
            await page.keyboard.press("PageDown")
            
            # Additional mouse wheel
            await page.mouse.wheel(0, 1000)

            await asyncio.sleep(random.uniform(2.5, 4.0)) # More time for network
            
            # Extract links
            new_links = await page.evaluate('''() => {
                const results = [];
                const anchors = document.querySelectorAll('a');
                for (const a of anchors) {
                    const href = a.getAttribute('href');
                    if (href && href.startsWith('/') && href.length > 2 && !href.includes('/p/') && !href.includes('/explore/') && !href.includes('/reels/')) {
                         const clean = href.split('?')[0].replace(/\/$/, "");
                         if (clean.split('/').length === 2) { // Just /username
                            results.push("https://www.instagram.com" + clean);
                         }
                    }
                }
                return results;
            }''')
            
            for link in new_links:
                if link.count('/') == 3:
                     discovered_profiles.add(link)
            
            # Stall Detection
            if i > 0 and len(discovered_profiles) == last_count:
                stall_streak += 1
            else:
                stall_streak = 0
            
            last_count = len(discovered_profiles)
            
            print(f"  Current count from {username} (Scroll {i+1}): {len(discovered_profiles)}", flush=True)
            
            if stall_streak >= 3:
                print(f"  Stall detected on {username}, skipping to next phase/influencer.", flush=True)
                break
                
            if len(discovered_profiles) >= MAX_FOLLOWERS_TO_SCRAPE:
                break
        return list(discovered_profiles)
    except Exception as e:
        print(f"Error expanding from {username}: {e}", flush=True)
        return []

async def main():
    if not os.path.exists(SEED_FILE):
        print(f"Seed file {SEED_FILE} not found. Please run profile_scraper.py first.")
        return

    # Load previously scraped influencers to expand from
    df = pd.read_csv(SEED_FILE)
    if df.empty:
        print(f"Seed file {SEED_FILE} is empty. No influencers to expand from.")
        return

    # Filter out already expanded ones
    expanded_list = []
    if os.path.exists(EXPANDED_FILE):
        with open(EXPANDED_FILE, "r") as f:
            expanded_list = [line.strip() for line in f if line.strip()]

    # Target large influencers first for better expansion, excluding already expanded
    mask = ~df["username"].isin(expanded_list)
    target_usernames = df[mask].sort_values(by="followers", ascending=False)["username"].head(20).tolist()
    
    if not target_usernames:
        print("No new influencers to expand from. Try scraping more profiles first.")
        return

    print(f"Targeting {len(target_usernames)} new influencers for expansion: {target_usernames}", flush=True)

    all_discovered = set()
    
    async with async_playwright() as p:
        browser, context = await get_logged_in_context(p, headless=True)
        page = await context.new_page()

        for username in target_usernames:
            print(f"Starting expansion for {username}...")
            try:
                profiles = await scrape_followers(page, username)
                if profiles:
                    print(f"  Found {len(profiles)} potential leads from {username}", flush=True)
                    all_discovered.update(profiles)
                    
                    # Incremental Saving
                    new_seeds_df = pd.DataFrame(list(profiles), columns=["profile_url"])
                    if os.path.exists(OUTPUT_FILE):
                        existing = pd.read_csv(OUTPUT_FILE)
                        combined = pd.concat([existing, new_seeds_df]).drop_duplicates()
                        combined.to_csv(OUTPUT_FILE, index=False)
                    else:
                        new_seeds_df.to_csv(OUTPUT_FILE, index=False)
                    print(f"  Incrementally saved {len(profiles)} leads to {OUTPUT_FILE}", flush=True)
                else:
                    print(f"  No leads found from {username}", flush=True)
                
                # Mark as expanded
                with open(EXPANDED_FILE, "a") as f:
                    f.write(f"{username}\n")
            except Exception as e:
                print(f"  Unhandled error during expansion for {username}: {e}")
            await asyncio.sleep(random.uniform(5, 10)) # Respectful delay

        print(f"Batch complete. Total leads discovered in this session: {len(all_discovered)}")
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
