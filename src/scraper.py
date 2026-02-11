import asyncio
from playwright.async_api import async_playwright
import datetime
import json
import re

JOB_URL = "https://apply.careers.microsoft.com/careers?query=Software+engineer&start=0&location=United+States&pid=1970393556752185&sort_by=timestamp&filter_include_remote=1"

# API endpoint used by the Microsoft Careers page (Phenom PCS platform)
SEARCH_API_URL = "https://apply.careers.microsoft.com/api/pcs/search"

# ---------------------------------------------------------------------------
# Title-level filter: keep only entry-to-mid level Software Engineer roles
# (e.g. "Software Engineer", "Software Engineer II") and exclude senior+.
# ---------------------------------------------------------------------------
EXCLUDE_TITLE_PATTERNS = re.compile(
    r"\b(senior|sr\.?|staff|principal|lead|manager|director|vp|distinguished|partner|architect)\b",
    re.IGNORECASE,
)


def is_target_level(title: str) -> bool:
    """Return True if *title* looks like an entry-to-mid level SWE role."""
    if "software engineer" not in title.lower():
        return False
    return not EXCLUDE_TITLE_PATTERNS.search(title)


async def get_latest_jobs():
    """
    Scrapes the Microsoft Careers page for the latest job postings.
    Uses API interception to capture the actual job data.
    Returns a list of dictionaries with job details.
    """
    jobs = []
    api_responses = []
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()
        
        # Intercept API responses to capture job data
        async def handle_response(response):
            if "/api/" in response.url and response.status == 200:
                try:
                    if "search" in response.url or "positions" in response.url:
                        data = await response.json()
                        api_responses.append({"url": response.url, "data": data})
                        print(f"Captured API response: {response.url[:80]}...")
                except Exception as e:
                    pass  # Not all responses are JSON
        
        page.on("response", handle_response)
        
        try:
            print(f"Navigating to {JOB_URL}...")
            await page.goto(JOB_URL, wait_until="networkidle", timeout=90000)
            
            # Wait for job content to load
            await page.wait_for_timeout(8000)
            
            # Try to extract jobs from API responses first (most reliable)
            for resp in api_responses:
                data = resp.get("data", {})
                
                # Handle different API response structures
                positions = None
                if isinstance(data, dict):
                    positions = data.get("positions") or data.get("jobs") or data.get("results")
                    if not positions and "data" in data:
                        positions = data["data"].get("positions") or data["data"].get("jobs")
                
                if positions and isinstance(positions, list):
                    print(f"Found {len(positions)} jobs in API response")
                    for pos in positions:
                        job_id = str(pos.get("id") or pos.get("jobId") or pos.get("requisitionId") or pos.get("position_id", ""))
                        title = pos.get("title") or pos.get("jobTitle") or pos.get("position_title") or pos.get("name", "Unknown Position")
                        location = pos.get("location") or pos.get("locations") or pos.get("city", "United States")
                        
                        # Handle location as list
                        if isinstance(location, list):
                            location = ", ".join([str(l.get("name", l) if isinstance(l, dict) else l) for l in location[:2]])
                        
                        link = pos.get("url") or pos.get("applyUrl") or pos.get("jobDetailUrl") or ""
                        if not link and job_id:
                            link = f"https://apply.careers.microsoft.com/careers/job/{job_id}"
                        
                        if job_id and not any(j["id"] == job_id for j in jobs) and is_target_level(str(title)):
                            jobs.append({
                                "id": job_id,
                                "title": str(title)[:100],
                                "location": str(location)[:100],
                                "link": link,
                                "found_at": datetime.datetime.now().isoformat()
                            })
            
            # If API interception didn't work, fall back to DOM scraping
            if not jobs:
                print("No API data captured, falling back to DOM scraping...")
                
                # Updated selectors for the new Microsoft Careers site (Phenom PCS platform)
                selectors_to_try = [
                    '[data-ph-at-id="job-card"]',
                    '[data-ph-at-id="jobs-list"] a',
                    'a[data-ph-at-id="job-link"]',
                    'div[class*="JobCard"]',
                    'div[class*="job-card"]',
                    '[class*="jobs-list"] a[href*="/job/"]',
                    'a[href*="/job/"]',
                    'article[class*="job"]',
                    'li[class*="job"]',
                    '[role="listitem"] a[href*="/job/"]',
                ]
                
                job_elements = []
                for selector in selectors_to_try:
                    try:
                        elements = await page.query_selector_all(selector)
                        if elements and len(elements) > 0:
                            print(f"Found {len(elements)} elements with selector: {selector}")
                            job_elements = elements
                            break
                    except Exception as e:
                        continue
                
                for elem in job_elements[:20]:
                    try:
                        # Get the href
                        href = await elem.get_attribute("href")
                        if not href:
                            link_elem = await elem.query_selector("a[href*='/job/']")
                            if link_elem:
                                href = await link_elem.get_attribute("href")
                        
                        if not href or "/job/" not in href:
                            continue
                        
                        # Make absolute URL
                        if href.startswith("/"):
                            href = "https://apply.careers.microsoft.com/careers" + href
                        
                        # Extract job ID
                        job_id = href.split("/job/")[-1].split("?")[0].split("/")[0]
                        
                        # Get title
                        title = "Software Engineer Position"
                        title_selectors = ['[data-ph-at-id="job-title"]', 'h2', 'h3', 'h4', '[class*="title"]', 'strong']
                        for sel in title_selectors:
                            try:
                                title_elem = await elem.query_selector(sel)
                                if title_elem:
                                    text = await title_elem.inner_text()
                                    if text and len(text) > 3:
                                        title = text.strip()
                                        break
                            except:
                                continue
                        
                        # Get location
                        location = "United States"
                        location_selectors = ['[data-ph-at-id="job-location"]', '[class*="location"]']
                        for sel in location_selectors:
                            try:
                                loc_elem = await elem.query_selector(sel)
                                if loc_elem:
                                    loc_text = await loc_elem.inner_text()
                                    if loc_text and len(loc_text) > 2:
                                        location = loc_text.strip()
                                        break
                            except:
                                continue
                        
                        if not any(j["id"] == job_id for j in jobs) and is_target_level(title):
                            jobs.append({
                                "id": job_id,
                                "title": title[:100],
                                "location": location[:100],
                                "link": href,
                                "found_at": datetime.datetime.now().isoformat()
                            })
                            print(f"  Added: {title[:50]}...")
                    except Exception as e:
                        print(f"Error parsing element: {e}")
                        continue
            
            # If still no jobs, try extracting from page's embedded JSON data
            if not jobs:
                print("Trying to extract from embedded JSON...")
                try:
                    # Look for __NEXT_DATA__ or any embedded JSON with job info
                    scripts = await page.query_selector_all("script")
                    for script in scripts:
                        try:
                            content = await script.inner_text()
                            if content and ("jobTitle" in content or "position_title" in content):
                                # Try to parse as JSON or find JSON within
                                json_matches = re.findall(r'\{[^{}]+(?:\{[^{}]*\}[^{}]*)*\}', content)
                                for match in json_matches:
                                    try:
                                        data = json.loads(match)
                                        if isinstance(data, dict) and any(k in data for k in ["jobTitle", "title", "position_title"]):
                                            job_id = str(data.get("id", hash(str(data)) % 100000))
                                            job_title = data.get("jobTitle") or data.get("title", "Unknown")
                                            if is_target_level(str(job_title)):
                                                jobs.append({
                                                    "id": job_id,
                                                    "title": job_title,
                                                    "location": data.get("location", "United States"),
                                                    "link": data.get("url", JOB_URL),
                                                    "found_at": datetime.datetime.now().isoformat()
                                                })
                                    except json.JSONDecodeError:
                                        continue
                        except:
                            continue
                except Exception as e:
                    print(f"Embedded JSON extraction failed: {e}")
                    
        except Exception as e:
            print(f"Error scraping jobs: {e}")
            import traceback
            traceback.print_exc()
            
        finally:
            await browser.close()
    
    print(f"Total jobs found: {len(jobs)}")
    return jobs

if __name__ == "__main__":
    jobs = asyncio.run(get_latest_jobs())
    print("\n=== Jobs Found ===")
    for j in jobs:
        print(f"- [{j['id']}] {j['title']} | {j['location']}")
        print(f"  Link: {j['link']}")
