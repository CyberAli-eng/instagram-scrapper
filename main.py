import asyncio
import pandas as pd
import os
from scraper.profile_scraper import scrape_profile
from utils.auth import get_logged_in_context
from playwright.async_api import async_playwright

async def worker(queue, context):
    """A worker that processes URLs from a queue using a shared browser context."""
    page = await context.new_page()
    while True:
        url = await queue.get()
        if url is None:
            break
            
        data = await scrape_profile(page, url)
        if data:
            # Append result
            pd.DataFrame([data]).to_csv(
                "data/influencers.csv", 
                mode='a', 
                header=not os.path.exists("data/influencers.csv"), 
                index=False
            )
        queue.task_done()
    await page.close()

async def run_parallel_scraping(num_workers=15):
    input_file = "data/seed_profiles.csv"
    output_file = "data/influencers.csv"
    
    if not os.path.exists(input_file):
        print("Discovery seeds not found.")
        return

    # 1. Load seeds and deduplicate
    df_seeds = pd.read_csv(input_file).drop_duplicates()
    urls = df_seeds["profile_url"].tolist()
    
    # 2. Filter out already scraped profiles
    if os.path.exists(output_file):
        df_existing = pd.read_csv(output_file).drop_duplicates(subset=["username"])
        df_existing.to_csv(output_file, index=False) # Clean it up
        if not df_existing.empty:
            existing_urls = set(df_existing["profile_url"].tolist())
            filtered_urls = [u for u in urls if u not in existing_urls]
            print(f"Skipping {len(urls) - len(filtered_urls)} already scraped profiles. New seeds to process: {len(filtered_urls)}")
            urls = filtered_urls

    if not urls:
        print("No new seeds to scrape.")
        return

    queue = asyncio.Queue()
    for url in urls:
        await queue.put(url)

    async with async_playwright() as p:
        browser, context = await get_logged_in_context(p, headless=True)
        
        # Start workers
        workers = [asyncio.create_task(worker(queue, context)) for _ in range(num_workers)]
        
        # Wait for queue to empty
        await queue.join()
        
        # Stop workers
        for _ in range(num_workers):
            await queue.put(None)
        await asyncio.gather(*workers)
        
        await browser.close()

if __name__ == "__main__":
    asyncio.run(run_parallel_scraping())
