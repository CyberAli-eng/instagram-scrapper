import asyncio
import os
import json
from playwright.async_api import async_playwright

# Configuration
SESSION_FILE = "data/session.json"
USERNAME = os.getenv("INSTAGRAM_USERNAME")
PASSWORD = os.getenv("INSTAGRAM_PASSWORD")

# Global lock to prevent concurrent login attempts
login_lock = asyncio.Lock()

async def login_and_save_session():
    """Logs into Instagram and saves the session storage to a file."""
    if not USERNAME or not PASSWORD:
        print("ERROR: INSTAGRAM_USERNAME and INSTAGRAM_PASSWORD environment variables are required.")
        return

    async with async_playwright() as p:
        # Run non-headless to see what's happening if needed, or headless for production
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
            viewport={'width': 1280, 'height': 800}
        )
        page = await context.new_page()

        try:
            print(f"Navigating to Instagram login for user: {USERNAME}")
            for retry in range(3):
                try:
                    await page.goto("https://www.instagram.com/accounts/login/", wait_until="domcontentloaded", timeout=60000)
                    break
                except Exception as e:
                    print(f"Navigation retry {retry+1} failing: {e}")
                    await asyncio.sleep(5)
            
            # Wait for any network activity to settle
            await page.wait_for_timeout(5000)
            
            # 1. Handle Cookie Consent if it appears
            try:
                # Instagram often shows a "Allow all cookies" or "Decline optional" dialog
                cookie_button = await page.wait_for_selector('button:has-text("Allow"), button:has-text("Accept"), button:has-text("Decline")', timeout=10000)
                if cookie_button:
                    print("Handling cookie consent dialog...")
                    await cookie_button.click()
                    await asyncio.sleep(2)
            except:
                pass 

            # 2. Fill in credentials
            print("Waiting for login form...")
            # Use extremely broad selectors as fallback
            try:
                username_field = await page.wait_for_selector('input[name="username"], input[aria-label*="Username"], input[type="text"], input[type="email"]', timeout=30000)
                print("Username field found.")
                await username_field.fill(USERNAME)
                
                password_field = await page.wait_for_selector('input[name="password"], input[aria-label*="Password"], input[type="password"]', timeout=10000)
                print("Password field found.")
                await password_field.fill(PASSWORD)
                
                # Click Login
                # Find any button that looks like a login button
                login_button = await page.wait_for_selector('button[type="submit"], button:has-text("Log in"), button:has-text("Log In")', timeout=10000)
                await login_button.click()
                print("Login button clicked, waiting for redirect...")
            except Exception as e:
                print(f"Could not find login fields: {e}")
                raise e

            # 3. Handle "Save Login Info" or "Turn on Notifications" prompts
            try:
                not_now_button = await page.wait_for_selector('button:has-text("Not Now"), div[role="button"]:has-text("Not Now")', timeout=15000)
                if not_now_button:
                    print("Skipping 'Save Login Info' prompt...")
                    await not_now_button.click()
                    await asyncio.sleep(2)
            except:
                pass

            # 4. Final verification
            try:
                # Wait for either home page elements OR the onetap URL which means we are past credentials
                await page.wait_for_selector('svg[aria-label="New post"], svg[aria-label="Home"], [aria-label*="Home"], [aria-label*="New Post"]', timeout=20000)
                print("Successfully logged in and reached home page!")
                
                # Save session state
                state = await context.storage_state()
                with open(SESSION_FILE, "w") as f:
                    json.dump(state, f)
                print(f"Session saved to {SESSION_FILE}")
            except Exception as e:
                # If we're at 'onetap' or 'done' page, it's a success
                if "instagram.com" in page.url and ("login" not in page.url or "onetap" in page.url):
                    print(f"Reached {page.url}, assuming logged in state.")
                    state = await context.storage_state()
                    with open(SESSION_FILE, "w") as f:
                        json.dump(state, f)
                    print(f"Session saved to {SESSION_FILE}")
                else:
                    raise e
            
        except Exception as e:
            print(f"Login process interrupted or failed: {e}")
            # If we are actually logged in but something else failed, let's try to save state anyway if it looks okay
            if "instagram.com" in page.url and "login" not in page.url:
                 state = await context.storage_state()
                 with open(SESSION_FILE, "w") as f:
                     json.dump(state, f)
                 print(f"Emergency session saved from: {page.url}")
            else:
                await page.screenshot(path="data/login_failed.png")
                print(f"Debug screenshot saved to data/login_failed.png")
                print(f"Stuck at: {page.url}")

        await browser.close()

async def get_logged_in_context(p, headless=True):
    """Utility to get an authenticated browser context from the saved session."""
    async with login_lock:
        if not os.path.exists(SESSION_FILE):
            print(f"Session file {SESSION_FILE} not found. Running login first...")
            await login_and_save_session()
        
    browser = await p.chromium.launch(headless=headless)
    
    if os.path.exists(SESSION_FILE):
        context = await browser.new_context(
            storage_state=SESSION_FILE,
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
        )
    else:
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
        )
        
    return browser, context

if __name__ == "__main__":
    if not os.path.exists('data'):
        os.makedirs('data')
    asyncio.run(login_and_save_session())
