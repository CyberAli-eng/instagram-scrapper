import asyncio
import csv
import os
import sys
import random

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from playwright.async_api import async_playwright
from utils.categories import NICHE_CATEGORIES, BEST_LEAD_GEN_NICHES, HIGH_VALUE_NICHE_MICRO_CATEGORIES

# Configuration
# Generate a comprehensive list of hashtags from ALL niches
HASHTAGS = []
for niche, tags in NICHE_CATEGORIES.items():
    HASHTAGS.extend([tag.lower().replace(" ", "") for tag in tags])

# Add high value micro categories as well
HASHTAGS.extend([tag.lower().replace(" ", "") for tag in HIGH_VALUE_NICHE_MICRO_CATEGORIES])

# Shuffle to ensure variety in each run
random.shuffle(HASHTAGS)

OUTPUT_FILE = "data/seed_profiles.csv"
MAX_POSTS_PER_TAG = 100 # Increased for better reach

async def scrape_hashtag(page, hashtag):
    print(f"Scraping hashtag: #{hashtag}")
    url = f"https://www.instagram.com/explore/tags/{hashtag}/"
    links = set()
    
    try:
        await page.goto(url, timeout=60000)
        # Human-like wait for initial load
        await asyncio.sleep(random.uniform(5, 10))

        # Scroll to collect posts
        for i in range(10): # Scroll more for more leads
            # Collect all 'a' tags that look like profile links or post links
            # Post links: /p/XYZ/
            # Profile links: /username/
            
            new_links = await page.evaluate('''() => {
                const results = [];
                // Look for all links
                const anchors = document.querySelectorAll('a');
                for (const a of anchors) {
                    const href = a.getAttribute('href');
                    if (!href) continue;
                    
                    // Instagram hashtag page links are usually /p/POST_ID/ or /username/
                    // But in the grid, the username isn't always directly in an 'a' tag.
                    // We can also look for aria-label or other indicators.
                    
                    if (href.startsWith('/') && href.length > 2) {
                        const parts = href.split('/').filter(p => p);
                        if (parts.length === 1 && !['explore', 'reels', 'direct', 'p'].includes(parts[0])) {
                           results.push("https://www.instagram.com/" + parts[0]);
                        }
                    }
                }
                return results;
            }''')
            
            for link in new_links:
                if link.count('/') == 3: # Basic profile link check
                    links.add(link)
            
            # Randomized scroll amount
            scroll_y = random.randint(1500, 3000)
            await page.mouse.wheel(0, scroll_y)
            
            # Randomized delay between scrolls
            await asyncio.sleep(random.uniform(3, 6))
            
            if len(links) >= MAX_POSTS_PER_TAG:
                break
                
        return list(links)
    except Exception as e:
        print(f"Error scraping #{hashtag}: {e}")
        return []

async def main():
    if not os.path.exists('data'):
        os.makedirs('data')

    async with async_playwright() as p:
        from utils.auth import get_logged_in_context
        browser, context = await get_logged_in_context(p)
        page = await context.new_page()

        all_profiles = set()
        for tag in HASHTAGS:
            profiles = await scrape_hashtag(page, tag)
            all_profiles.update(profiles)
            print(f"  Found {len(profiles)} profiles for #{tag}")
            await asyncio.sleep(5)

        if all_profiles:
            file_exists = os.path.exists(OUTPUT_FILE)
            with open(OUTPUT_FILE, "a", newline="") as f:
                writer = csv.writer(f)
                if not file_exists:
                    writer.writerow(["profile_url"])
                for profile in all_profiles:
                    writer.writerow([profile])
            print(f"Appended {len(all_profiles)} profiles to {OUTPUT_FILE}")
        else:
            print("No new profiles found in this hashtag run.")
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
