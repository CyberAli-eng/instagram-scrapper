import asyncio
import pandas as pd
import os
import re
import random
import sys

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from playwright.async_api import async_playwright
from utils.auth import get_logged_in_context

# Configuration
INPUT_FILE = "data/seed_profiles.csv"
OUTPUT_FILE = "data/influencers.csv"
MIN_FOLLOWERS = 1000

def extract_email(text):
    """Robust email extraction from text, handling common obfuscations or simple regex."""
    emails = re.findall(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", text)
    return emails[0] if emails else ""

def parse_followers(text):
    """Robust follower parsing for multiple formats (K, M, B, etc.)."""
    # Look for "Followers" text often found in meta tags or page content
    match = re.search(r'([\d,.]+)([KMB]?) Followers', text, re.I)
    if not match:
        # Try finding it in page JSON or other patterns if needed
        return 0

    num_str = match.group(1).replace(",", "")
    try:
        num = float(num_str)
    except ValueError:
        return 0
        
    suffix = match.group(2).upper()

    if suffix == "K":
        num *= 1000
    elif suffix == "M":
        num *= 1000000
    elif suffix == "B":
        num *= 1000000000

    return int(num)

async def human_delay(min_s=2, max_s=5):
    """Randomized delay to mimic human reading/browsing time (tightened for speed)."""
    delay = random.uniform(min_s, max_s)
    await asyncio.sleep(delay)

async def human_interaction(page):
    """Mimic subtle human mouse movements and small scrolls."""
    try:
        # Avoid jitter if page is closed
        if page.is_closed(): return
        
        # Micro-scroll
        scroll_amount = random.randint(100, 400)
        await page.mouse.wheel(0, scroll_amount)
        await asyncio.sleep(random.uniform(0.1, 0.5))
        await page.mouse.wheel(0, -random.randint(50, 200)) # Small scroll back up
        
        # Subtle mouse move (jitter)
        # Move mouse to a few random points on screen
        for _ in range(random.randint(1, 3)):
            x = random.randint(100, 1000)
            y = random.randint(100, 600)
            await page.mouse.move(x, y, steps=5)
            await asyncio.sleep(random.uniform(0.05, 0.15))
    except:
        pass

async def scrape_profile(page, url):
    """Scrapes a single Instagram profile with retry logic and randomization."""
    print(f"Scraping: {url}")
    
    for attempt in range(4): # Increased to 4 attempts
        try:
            # Human-like start delay
            await human_delay(1, 3)
            
            await page.goto(url, timeout=60000)
            await page.wait_for_timeout(random.randint(800, 1500))
            
            # 1. Block/Checkpoint Detection
            current_html = await page.content()
            if "Please wait a few minutes before you try again" in current_html or "Too Many Requests" in current_html:
                wait_time = random.randint(300, 600) # 5-10 minutes
                print(f"  BLOCK DETECTED! Cool-down for {wait_time//60} mins...")
                await asyncio.sleep(wait_time)
                continue

            if "login" in page.url and "login" not in url:
                print(f"  REDIRECTED to login for {url}. Attempt {attempt+1}")
                await asyncio.sleep(20)
                continue
            
            # 2. Human Interactions (Reduced for speed)
            await human_interaction(page)
            await human_delay(1, 2)

            # 3. Data Extraction
            html = await page.content()
            followers = parse_followers(html)

            if followers < MIN_FOLLOWERS:
                print(f"  Skipping {url}: Only {followers} followers.")
                return None

            email = extract_email(html)
            username = url.rstrip("/").split("/")[-1]
            
            # Use evaluate for more complex logic
            data = await page.evaluate('''() => {
                const meta = document.querySelector('meta[name="description"]');
                const bio = meta ? meta.getAttribute('content') : '';
                return { bio };
            }''')

            return {
                "username": username,
                "profile_url": url,
                "followers": followers,
                "email": email,
                "bio": data['bio'],
                "category": "", 
                "city": "India",
                "scraped_at": pd.Timestamp.now().isoformat()
            }

        except Exception as e:
            print(f"  Error on attempt {attempt+1} for {url}: {e}")
            await asyncio.sleep(random.randint(15, 30))
            
    return None

async def main():
    if not os.path.exists(INPUT_FILE):
        print(f"Input file {INPUT_FILE} not found. Please run discovery first.")
        return

    df = pd.read_csv(INPUT_FILE)
    urls = df["profile_url"].tolist()

    results = []
    
    async with async_playwright() as p:
        # Use logged-in context
        browser, context = await get_logged_in_context(p, headless=True)
        page = await context.new_page()

        for url in urls:
            data = await scrape_profile(page, url)
            if data:
                results.append(data)
                print(f"  Added: {data['username']} ({data['followers']} followers)")
                
                # Intermediate save to avoid data loss (Append strategy)
                pd.DataFrame([data]).to_csv(
                    OUTPUT_FILE, 
                    mode='a', 
                    header=not os.path.exists(OUTPUT_FILE), 
                    index=False
                )

        await browser.close()

    print(f"DONE: Scraped {len(results)} influencers.")

if __name__ == "__main__":
    asyncio.run(main())
