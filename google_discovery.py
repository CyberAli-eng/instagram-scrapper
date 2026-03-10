import asyncio
import csv
from playwright.async_api import async_playwright

QUERIES = [
    'site:instagram.com "beauty" "India" "gmail.com"',
    'site:instagram.com "fashion blogger" "Delhi"',
    'site:instagram.com "makeup artist" "Mumbai"',
    'site:instagram.com "luxary vlog" "Bombay"'
]

OUTPUT = "data/seed_profiles.csv"


async def search_google(page, query):
    url = f"https://www.google.com/search?q={query}"
    
    try:
        await page.goto(url, timeout=60000)
        await page.wait_for_timeout(3000)

        # Check for CAPTCHA
        content = await page.content()
        if "captcha" in content.lower() or "google.com/sorry" in url:
            print(f"  BLOCKED: Google CAPTCHA detected for {query}")
            return []

        # Extract all links that contain instagram.com
        links = await page.evaluate('''() => {
            const results = [];
            const anchors = document.querySelectorAll('a');
            for (const a of anchors) {
                const href = a.href;
                if (href && href.includes('instagram.com') && !href.includes('/p/') && !href.includes('/reels/') && !href.includes('/explore/')) {
                    // Clean URL
                    try {
                        const clean = href.split('?')[0].replace(/\/$/, "");
                        if (clean.split('/').length >= 4) {
                            results.push(clean);
                        }
                    } catch (e) {}
                }
            }
            return results;
        }''')
        
        # Fallback if evaluation fails or returns empty (simple selector search)
        if not links:
            anchors = await page.query_selector_all("a")
            for a in anchors:
                href = await a.get_attribute("href")
                if href and "instagram.com" in href and "/p/" not in href and "/reels/" not in href and "/explore/" not in href:
                    clean = href.split("?")[0].rstrip("/")
                    if clean.count("/") >= 3:
                        links.append(clean)
        
        if not links:
            print(f"  No links found in HTML of length {len(content)}")
            # Optional: save current page state for debugging
            # await page.screenshot(path=f"debug_{query[:10]}.png")

        return list(set(links))
    except Exception as e:
        print(f"Error searching {query}: {e}")
        return []


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        # Set a realistic user agent
        await page.set_extra_http_headers({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
        })

        all_links = []

        for q in QUERIES:
            print("Searching:", q)
            links = await search_google(page, q)
            all_links.extend(links)
            print(f"  Found {len(links)} links")
            await asyncio.sleep(5)

        all_links = list(set(all_links))

        with open(OUTPUT, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["profile_url"])
            for link in all_links:
                writer.writerow([link])

        print("Saved:", len(all_links))
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())