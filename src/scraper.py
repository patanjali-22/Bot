import asyncio
from playwright.async_api import async_playwright
import datetime
import re

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
            print(f"Navigating to {JOB_URL}...")
            await page.goto(JOB_URL, wait_until="networkidle", timeout=60000)
            
            # Wait extra time for JavaScript to render
            await page.wait_for_timeout(5000)
            
            # Try multiple selector strategies
            job_cards = []
            
            # Strategy 1: Look for job cards by common class patterns
            selectors_to_try = [
                'div[data-automation-id="jobCard"]',
                '[class*="jobCard"]',
                '[class*="job-card"]', 
                '[class*="JobCard"]',
                'article[class*="job"]',
                'div[role="listitem"]',
                'li[class*="job"]',
                'a[href*="/job/"]',
                '[class*="searchResults"] a[href*="/job/"]',
            ]
            
            for selector in selectors_to_try:
                try:
                    elements = await page.query_selector_all(selector)
                    if elements and len(elements) > 0:
                        print(f"Found {len(elements)} elements with selector: {selector}")
                        job_cards = elements
                        break
                except Exception as e:
                    continue
            
            if not job_cards:
                # Strategy 2: Find all links that look like job links
                print("Trying to find job links directly...")
                all_links = await page.query_selector_all('a[href*="/job/"]')
                if all_links:
                    print(f"Found {len(all_links)} job links")
                    job_cards = all_links
            
            if not job_cards:
                # Strategy 3: Get the page content and look for patterns
                print("Falling back to content analysis...")
                content = await page.content()
                
                # Look for job URLs in the page content
                job_url_pattern = r'href="(/job/[^"]+)"'
                matches = re.findall(job_url_pattern, content)
                
                if matches:
                    print(f"Found {len(matches)} job URLs in page content")
                    unique_urls = list(set(matches))
                    
                    for url in unique_urls[:20]:  # Limit to 20 jobs
                        full_url = "https://apply.careers.microsoft.com/careers" + url if url.startswith("/") else url
                        job_id = url.split("/")[-1].split("?")[0]
                        
                        jobs.append({
                            "id": job_id,
                            "title": f"Software Engineer Position ({job_id[:8]}...)",
                            "location": "United States (Remote Available)",
                            "link": full_url,
                            "found_at": datetime.datetime.now().isoformat()
                        })
                    
                    print(f"Extracted {len(jobs)} jobs from URL patterns")
                    return jobs
            
            print(f"Processing {len(job_cards)} job cards...")
            
            for card in job_cards:
                try:
                    # Try to get the href directly if it's a link
                    link = None
                    tag_name = await card.evaluate("el => el.tagName.toLowerCase()")
                    
                    if tag_name == "a":
                        link = await card.get_attribute("href")
                    else:
                        # Look for a link within the card
                        link_elem = await card.query_selector("a[href*='/job/']")
                        if link_elem:
                            link = await link_elem.get_attribute("href")
                    
                    if not link or "/job/" not in link:
                        continue
                    
                    # Make link absolute
                    if link.startswith("/"):
                        link = "https://apply.careers.microsoft.com/careers" + link
                    
                    # Extract job ID from link
                    job_id = link.split("/job/")[-1].split("?")[0].split("/")[0]
                    
                    # Try to get title
                    title = "Software Engineer Position"
                    title_selectors = ["h2", "h3", "h4", "[class*='title']", "[class*='Title']", "strong"]
                    for sel in title_selectors:
                        try:
                            title_elem = await card.query_selector(sel)
                            if title_elem:
                                title_text = await title_elem.inner_text()
                                if title_text and len(title_text) > 5:
                                    title = title_text.strip()
                                    break
                        except:
                            continue
                    
                    # Try to get location
                    location = "United States"
                    text_content = await card.inner_text()
                    
                    # Look for location patterns
                    location_patterns = [
                        r"(Remote|Hybrid|On-Site)",
                        r"(United States|USA|US)",
                        r"([A-Z][a-z]+,\s*[A-Z]{2})",  # City, State
                    ]
                    for pattern in location_patterns:
                        match = re.search(pattern, text_content)
                        if match:
                            location = match.group(0)
                            break
                    
                    job = {
                        "id": job_id,
                        "title": title[:100],  # Limit title length
                        "location": location,
                        "link": link,
                        "found_at": datetime.datetime.now().isoformat()
                    }
                    
                    # Avoid duplicates
                    if not any(j["id"] == job_id for j in jobs):
                        jobs.append(job)
                        print(f"  Added: {title[:50]}...")
                    
                except Exception as e:
                    print(f"Error parsing card: {e}")
                    continue
            
            # If still no jobs, try to extract from page's JavaScript state
            if not jobs:
                print("Attempting to extract from JavaScript state...")
                try:
                    # Look for __NEXT_DATA__ or similar
                    script_data = await page.evaluate("""
                        () => {
                            const scripts = document.querySelectorAll('script');
                            for (const script of scripts) {
                                if (script.textContent && script.textContent.includes('jobTitle')) {
                                    return script.textContent;
                                }
                            }
                            return null;
                        }
                    """)
                    
                    if script_data:
                        # Extract job titles from the script content
                        title_matches = re.findall(r'"jobTitle"\s*:\s*"([^"]+)"', script_data)
                        link_matches = re.findall(r'"jobPostingUrl"\s*:\s*"([^"]+)"', script_data)
                        
                        for i, title in enumerate(title_matches[:20]):
                            link = link_matches[i] if i < len(link_matches) else ""
                            job_id = f"extracted_{i}_{hash(title) % 10000}"
                            
                            jobs.append({
                                "id": job_id,
                                "title": title,
                                "location": "United States",
                                "link": link if link else JOB_URL,
                                "found_at": datetime.datetime.now().isoformat()
                            })
                        
                        print(f"Extracted {len(jobs)} jobs from JavaScript state")
                except Exception as e:
                    print(f"JavaScript extraction failed: {e}")
                    
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
    for j in jobs:
        print(f"- {j['title']} | {j['location']} | {j['link']}")
