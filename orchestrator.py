import os
import subprocess
import time
import pandas as pd

# Load .env variables manually to ensure subprocesses have them
def load_env():
    if os.path.exists(".env"):
        with open(".env", "r") as f:
            for line in f:
                if "=" in line:
                    key, value = line.strip().split("=", 1)
                    os.environ[key] = value

def run_script(script_path):
    print(f"\n{'='*20}")
    print(f"RUNNING: {script_path}")
    print(f"{'='*20}\n")
    try:
        # Use venv python for stability
        python_executable = os.path.join(os.getcwd(), "venv/bin/python3")
        subprocess.run([python_executable, "-u", script_path], check=True)
    except subprocess.CalledProcessError as e:
        print(f"Error running {script_path}: {e}")
    except Exception as e:
        print(f"Unexpected error: {e}")

def cleanup_seeds():
     # After scraping, we should clear the seeds so the next expansion cycle starts fresh
     # but we might want to keep them for debugging? Let's just rename for now.
     seed_file = "data/seed_profiles.csv"
     if os.path.exists(seed_file):
         timestamp = int(time.time())
         history_dir = "data/history"
         if not os.path.exists(history_dir):
             os.makedirs(history_dir)
         os.rename(seed_file, f"{history_dir}/seeds_{timestamp}.csv")
         print(f"Moved processed seeds to {history_dir}/seeds_{timestamp}.csv")

def main():
    load_env()
    cycle = 1
    while True:
        print(f"\n{'#'*40}")
        # 0. Bootstrap Authorities (Only once or if needed)
        # We want to make sure our new authority accounts are in the influencers.csv
        # so that follower_scraper.py can expand from them.
        authority_seeds = [
            "technicalguruji", "ranveerallahbadia", "komalpandeyofficial", "masabagupta",
            "mostlysane", "kushakapila", "ankurwarikoo", "financewithsharan", "dollysingh",
            "niharika_nm", "carryminati", "ig_mortal", "ranveer.brar", "kunalkapur",
            "mipalkarofficial", "diipakhosla", "houseofmisu", "malvikasitlaniofficial",
            "shereenlovebug", "santoshishetty", "juhigodambe", "shivammalik09",
            "abhiandniyu", "beerbiceps", "rajivmakhni", "fayedsouza", "barkhasingh0308",
            "shenaztreasury", "bruisedpassports", "curly.tales"
        ]
        if os.path.exists("data/influencers.csv"):
            df_inf = pd.read_csv("data/influencers.csv")
            existing_usernames = set(df_inf["username"].tolist())
            new_rows = []
            for u in authority_seeds:
                if u not in existing_usernames:
                    new_rows.append({
                        "username": u,
                        "profile_url": f"https://www.instagram.com/{u}",
                        "followers": 1000000, # Placeholder to ensure they are picked up as "large"
                        "email": "", "bio": "Bootstrapped authority", "category": "", "city": "India",
                        "scraped_at": pd.Timestamp.now().isoformat()
                    })
            if new_rows:
                pd.DataFrame(new_rows).to_csv("data/influencers.csv", mode='a', header=False, index=False)
                print(f"Bootstrapped {len(new_rows)} authorities into data/influencers.csv")

        # We've pivoted to deep follower expansion from authorities
        # run_script("discovery/hashtag_discovery.py")
        
        # 2. Expansion: Find new seeds from existing influencers
        run_script("scraper/follower_scraper.py")
        
        # 3. Scraping: Get details for all found seeds
        run_script("main.py")
        
        # 3. Progress Check
        if os.path.exists("data/influencers.csv"):
            df = pd.read_csv("data/influencers.csv")
            print(f"\n[PROGRESS] Current total influencers: {len(df)}")
            if len(df) >= 50000:
                print("TARGET REACHED! Stopping.")
                break
        
        # 4. Cleanup
        cleanup_seeds()
        
        print("\nCycle complete. Cooling down for 1 minute...")
        time.sleep(60) 
        cycle += 1

if __name__ == "__main__":
    main()
