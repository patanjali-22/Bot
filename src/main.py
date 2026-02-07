import json
import os
import asyncio
from scraper import get_latest_jobs
from emailer import send_email

DATA_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "known_jobs.json")

def load_known_jobs():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            try:
                return set(json.load(f))
            except json.JSONDecodeError:
                return set()
    return set()

def save_known_jobs(known_jobs):
    with open(DATA_FILE, "w") as f:
        json.dump(list(known_jobs), f)

async def main():
    print("Starting job check...")
    
    # 1. Load known jobs
    known_jobs = load_known_jobs()
    print(f"Loaded {len(known_jobs)} known jobs.")

    # 2. Scrape new jobs
    current_jobs = await get_latest_jobs()
    
    if not current_jobs:
        print("No jobs found or scraping failed.")
        return

    # 3. Find new jobs
    new_jobs = []
    new_job_ids = set()

    for job in current_jobs:
        job_id = job.get("id")
        if job_id and job_id not in known_jobs:
            new_jobs.append(job)
            new_job_ids.add(job_id)
        
        # Also keep track of all current IDs to save later 
        # (Optional: we might want to keep old IDs to avoid re-alerting if a job is reposted)
        # For now, let's just add new ones to our set
        if job_id:
             known_jobs.add(job_id)

    # 4. JSON file will just grow with IDs. 
    # That's fine for text IDs, it won't get too big too fast.
    
    if new_jobs:
        print(f"Found {len(new_jobs)} new jobs!")
        
        # 5. Send Email
        send_email(new_jobs)
        
        # 6. Save new state
        save_known_jobs(known_jobs)
        print("Updated known jobs file.")
        
    else:
        print("No new jobs found since last run.")

if __name__ == "__main__":
    asyncio.run(main())
