import asyncio
from playwright.async_api import async_playwright
import datetime

JOB_URL = "https://apply.careers.microsoft.com/careers?query=Software+engineer&start=0&location=United+States&pid=1970393556752185&sort_by=timestamp&filter_include_remote=1"

async def get_latest_jobs():
    """
    Scrapes the Microsoft Careers page for the latest job postings.
    Returns a list of dictionaries with job details.
    """
    jobs = []
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        try:
            # Go to the URL
            print(f"Navigating to {JOB_URL}...")
            await page.goto(JOB_URL, wait_until="networkidle")
            
            # Wait for job cards to load
            # The structure based on previous inspection seems to use standard job cards. 
            # We'll look for elements that likely contain job info.
            # Usually these are inside a list or grid.
            
            # Let's wait for a specific element that indicates jobs are loaded.
            # Based on common Microsoft career sites, usually job-item or similar class.
            # Since we don't have the exact selector, we'll wait for a generic container or text.
            await page.wait_for_selector('div[role="list"]', timeout=30000)
            
            # Extract job cards
            # This selector is an assumption based on common ARIA roles for lists of items
            job_cards = await page.query_selector_all('div[role="listitem"]')
            
            print(f"Found {len(job_cards)} job cards.")
            
            for card in job_cards:
                try:
                    # Extract Title
                    title_elem = await card.query_selector("h3") or await card.query_selector("h2")
                    title = await title_elem.inner_text() if title_elem else "Unknown Title"
                    
                    # Extract Link
                    link_elem = await card.query_selector("a")
                    link = await link_elem.get_attribute("href") if link_elem else ""
                    if link and not link.startswith("http"):
                        link = "https://apply.careers.microsoft.com" + link
                        
                    # Extract Job ID from link or other attribute
                    job_id = link.split("/")[-1] if link else "unknown_id"
                    
                    # Extract Location
                    # Usually in a span or div near the title
                    text_content = await card.inner_text()
                    lines = text_content.split('\n')
                    location = lines[1] if len(lines) > 1 else "Unknown Location"
                    
                    # Create job object
                    job = {
                        "id": job_id,
                        "title": title,
                        "location": location,
                        "link": link,
                        "found_at": datetime.datetime.now().isoformat()
                    }
                    jobs.append(job)
                    
                except Exception as e:
                    print(f"Error parsing card: {e}")
                    continue
                    
        except Exception as e:
            print(f"Error scraping jobs: {e}")
            
        finally:
            await browser.close()
            
    return jobs

if __name__ == "__main__":
    jobs = asyncio.run(get_latest_jobs())
    for j in jobs:
        print(j)
