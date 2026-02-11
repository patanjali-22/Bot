import json
import os
import asyncio
from scraper import get_latest_jobs as get_microsoft_jobs
from amazon_scraper import get_latest_jobs as get_amazon_jobs
from emailer import send_email

# Ensure data directory exists
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
MICROSOFT_DATA_FILE = os.path.join(DATA_DIR, "known_jobs.json")
AMAZON_DATA_FILE = os.path.join(DATA_DIR, "known_amazon_jobs.json")


def ensure_data_dir():
    """Ensure the data directory exists."""
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)
        print(f"Created data directory: {DATA_DIR}")


def load_known_jobs(filepath):
    """Load previously seen job IDs from a JSON file."""
    ensure_data_dir()
    if os.path.exists(filepath):
        with open(filepath, "r") as f:
            try:
                data = json.load(f)
                if isinstance(data, list):
                    valid_ids = [job_id for job_id in data if job_id and job_id != "unknown_id"]
                    return set(valid_ids)
                return set()
            except json.JSONDecodeError:
                print(f"Warning: Could not parse {filepath}, starting fresh")
                return set()
    return set()


def save_known_jobs(known_jobs, filepath):
    """Save known job IDs to a JSON file."""
    ensure_data_dir()
    with open(filepath, "w") as f:
        json.dump(sorted(list(known_jobs)), f, indent=2)
    print(f"Saved {len(known_jobs)} job IDs to {filepath}")


async def check_source(source_name, scrape_fn, data_file):
    """
    Run the scrape → diff → return-new-jobs pipeline for one source.
    Returns (new_jobs list, updated known_jobs set).
    """
    print(f"\n{'─' * 50}")
    print(f"  {source_name}")
    print(f"{'─' * 50}")

    known_jobs = load_known_jobs(data_file)
    print(f"Loaded {len(known_jobs)} previously seen {source_name} jobs.")

    print(f"Scraping {source_name} Careers page...")
    current_jobs = await scrape_fn()

    if not current_jobs:
        print(f"\n❌ No {source_name} jobs found or scraping failed.")
        return [], known_jobs

    print(f"✓ Found {len(current_jobs)} {source_name} jobs on the page")

    new_jobs = []
    for job in current_jobs:
        job_id = job.get("id")
        if job_id and job_id not in known_jobs:
            new_jobs.append(job)
            known_jobs.add(job_id)
            print(f"  NEW: {job.get('title', 'Unknown')[:50]}...")
        else:
            if job_id:
                known_jobs.add(job_id)

    if new_jobs:
        print(f"\n🎉 {len(new_jobs)} NEW {source_name} job(s)!")
        for i, job in enumerate(new_jobs, 1):
            print(f"  {i}. {job.get('title', 'Unknown Position')}")
            print(f"     Location: {job.get('location', 'N/A')}")
            print(f"     Link: {job.get('link', 'N/A')}")
    else:
        print(f"No new {source_name} jobs since last check.")

    # Always persist so newly validated IDs are saved
    save_known_jobs(known_jobs, data_file)
    return new_jobs, known_jobs


async def main():
    print("=" * 50)
    print("Job Alert Bot - Starting combined job check...")
    print("  Sources: Microsoft + Amazon")
    print("=" * 50)

    # --- Microsoft ---
    ms_new, _ = await check_source(
        "Microsoft", get_microsoft_jobs, MICROSOFT_DATA_FILE
    )

    # --- Amazon ---
    amz_new, _ = await check_source(
        "Amazon", get_amazon_jobs, AMAZON_DATA_FILE
    )

    # --- Combined email ---
    all_new = []
    for job in ms_new:
        job["company"] = "Microsoft"
        all_new.append(job)
    for job in amz_new:
        job["company"] = "Amazon"
        all_new.append(job)

    if all_new:
        print(f"\n📬 Sending single email with {len(all_new)} new job(s)...")
        email_sent = send_email(all_new)
        if email_sent:
            print("✓ Email sent successfully!")
        else:
            print("⚠ Email sending failed or skipped (check email configuration)")
    else:
        print("\nNo new jobs from any source. No email sent.")

    print("\n" + "=" * 50)
    print("Job check complete!")
    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(main())
