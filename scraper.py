import re
import asyncio
import pandas as pd
from playwright.async_api import async_playwright

INPUT_FILE = "seed_profiles.csv"
OUTPUT_FILE = "influencers.csv"

MIN_FOLLOWERS = 1000


def extract_email(text):
    emails = re.findall(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", text)
    return emails[0] if emails else ""


def parse_followers(text):
    match = re.search(r'([\d,.]+)([KMB]?) Followers', text, re.I)
    if not match:
        return 0

    num = float(match.group(1).replace(",", ""))
    suffix = match.group(2).upper()

    if suffix == "K":
        num *= 1000
    elif suffix == "M":
        num *= 1000000
    elif suffix == "B":
        num *= 1000000000

    return int(num)


async def scrape_profile(page, url):

    try:
        await page.goto(url, timeout=60000)
        await page.wait_for_timeout(3000)

        html = await page.content()

        followers = parse_followers(html)

        if followers < MIN_FOLLOWERS:
            return None

        email = extract_email(html)

        username = url.rstrip("/").split("/")[-1]

        return {
            "username": username,
            "profile_url": url,
            "followers": followers,
            "email": email,
            "bio": "",
            "category": "",
            "city": "India"
        }

    except:
        return None


async def main():

    df = pd.read_csv(INPUT_FILE)
    urls = df["profile_url"].tolist()

    results = []

    async with async_playwright() as p:

        browser = await p.chromium.launch(
            headless=False,
            args=["--disable-dev-shm-usage", "--no-sandbox"]
        )

        page = await browser.new_page()

        for url in urls:

            data = await scrape_profile(page, url)

            if data:
                results.append(data)
                print("Added:", data["username"])

        await browser.close()

    pd.DataFrame(results).to_csv(OUTPUT_FILE, index=False)

    print("DONE:", len(results))


asyncio.run(main())