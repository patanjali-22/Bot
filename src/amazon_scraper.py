import asyncio
import datetime
import os
from typing import Any, Dict, List, Optional

from playwright.async_api import async_playwright


# Amazon Jobs search UI and (often-used) JSON endpoint.
# We try the JSON endpoint first (fast + reliable), then fall back to loading the page
# and intercepting the XHR response if the endpoint/params change.
SEARCH_PAGE_URL = "https://www.amazon.jobs/en/search"
SEARCH_JSON_URL = "https://www.amazon.jobs/en/search.json"


def _env(name: str, default: str) -> str:
    v = (os.environ.get(name) or "").strip()
    return v if v else default


def build_search_params() -> Dict[str, str]:
    """
    Build Amazon Jobs search params.

    You can override behavior via env vars:
    - AMAZON_BASE_QUERY (default: "Software Engineer")
    - AMAZON_SORT       (default: "recent")
    - AMAZON_OFFSET     (default: "0")
    - AMAZON_RESULT_LIMIT (default: "25")
    """
    return {
        "base_query": _env("AMAZON_BASE_QUERY", "Software Engineer"),
        "sort": _env("AMAZON_SORT", "recent"),
        "offset": _env("AMAZON_OFFSET", "0"),
        "result_limit": _env("AMAZON_RESULT_LIMIT", "50"),
    }


def _as_str(x: Any) -> str:
    return "" if x is None else str(x)


def _first(*vals: Any) -> str:
    for v in vals:
        s = _as_str(v).strip()
        if s:
            return s
    return ""


def _normalize_location(raw: Any) -> str:
    # Location sometimes appears as a string, a dict, or a list of dicts/strings.
    if raw is None:
        return ""
    if isinstance(raw, str):
        return raw.strip()
    if isinstance(raw, dict):
        return _first(raw.get("name"), raw.get("location"), raw.get("value"))
    if isinstance(raw, list):
        parts: List[str] = []
        for item in raw[:2]:
            parts.append(_normalize_location(item))
        parts = [p for p in parts if p]
        return ", ".join(parts)
    return _as_str(raw).strip()


def normalize_job(pos: Dict[str, Any]) -> Optional[Dict[str, str]]:
    # Amazon's API returns two IDs:
    #   "id"       – a UUID (not usable in URLs)
    #   "id_icims" – the numeric posting ID used in the canonical URL
    # We prefer id_icims as the stable, URL-friendly identifier.
    job_id = _first(
        pos.get("id_icims"),
        pos.get("idIcims"),
        pos.get("requisitionId"),
        pos.get("requisition_id"),
        pos.get("jobId"),
        pos.get("job_id"),
        pos.get("postingId"),
        pos.get("posting_id"),
        pos.get("id"),
    )
    job_id = job_id.strip()
    if not job_id:
        return None

    title = _first(
        pos.get("title"),
        pos.get("jobTitle"),
        pos.get("job_title"),
        pos.get("name"),
        pos.get("positionTitle"),
    )[:100]

    location = _normalize_location(
        pos.get("location")
        or pos.get("normalized_location")
        or pos.get("primaryLocation")
        or pos.get("primary_location")
    )[:100]

    # Build the link.  The API provides "job_path" which is the exact
    # relative URL to the posting (e.g. /en/jobs/3179205/software-dev-engineer).
    # Fall back to constructing it from the numeric id.
    job_path = _first(pos.get("job_path"), pos.get("jobPath"))
    if job_path:
        link = "https://www.amazon.jobs" + (job_path if job_path.startswith("/") else "/" + job_path)
    else:
        link = _first(pos.get("url"), pos.get("jobDetailUrl"), pos.get("job_detail_url"))
        if link and link.startswith("/"):
            link = "https://www.amazon.jobs" + link
        if not link:
            link = f"https://www.amazon.jobs/en/jobs/{job_id}"

    return {
        "id": job_id,
        "title": title or "Unknown Position",
        "location": location or "N/A",
        "link": link,
        "found_at": datetime.datetime.now().isoformat(),
    }


def extract_positions(data: Any) -> List[Dict[str, Any]]:
    """
    Amazon's response shape can vary. This tries a few common structures:
    - { "jobs": [ ... ] }
    - { "results": [ ... ] }
    - { "search_results": { "jobs": [ ... ] } }
    - Elasticsearch-like: { "hits": { "hits": [ { "_source": ... }, ... ] } }
    """
    if not isinstance(data, dict):
        return []

    for key in ("jobs", "results", "positions"):
        v = data.get(key)
        if isinstance(v, list):
            return v

    sr = data.get("search_results") or data.get("searchResults") or data.get("data")
    if isinstance(sr, dict):
        for key in ("jobs", "results", "positions"):
            v = sr.get(key)
            if isinstance(v, list):
                return v

    hits = data.get("hits")
    if isinstance(hits, dict) and isinstance(hits.get("hits"), list):
        out: List[Dict[str, Any]] = []
        for h in hits["hits"]:
            if isinstance(h, dict):
                src = h.get("_source")
                if isinstance(src, dict):
                    out.append(src)
        return out

    return []


async def _try_fetch_json(params: Dict[str, str]) -> List[Dict[str, str]]:
    async with async_playwright() as p:
        req = await p.request.new_context()
        try:
            resp = await req.get(SEARCH_JSON_URL, params=params, timeout=90_000)
            if not resp.ok:
                return []
            data = await resp.json()
        except Exception:
            return []
        finally:
            await req.dispose()

    positions = extract_positions(data)
    jobs: List[Dict[str, str]] = []
    seen: set[str] = set()
    for pos in positions:
        if not isinstance(pos, dict):
            continue
        j = normalize_job(pos)
        if not j:
            continue
        if j["id"] in seen:
            continue
        seen.add(j["id"])
        jobs.append(j)
    return jobs


async def _try_intercept_from_page(params: Dict[str, str]) -> List[Dict[str, str]]:
    jobs: List[Dict[str, str]] = []
    api_payloads: List[Any] = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()

        async def handle_response(response):
            url = response.url
            if response.status != 200:
                return
            # Be flexible: capture likely JSON search responses.
            if "search.json" not in url and "/api/" not in url and "search" not in url:
                return
            try:
                api_payloads.append(await response.json())
            except Exception:
                return

        page.on("response", handle_response)

        try:
            # Build the UI URL (Playwright will encode params)
            print(f"Navigating to {SEARCH_PAGE_URL} ...")
            await page.goto(SEARCH_PAGE_URL, wait_until="networkidle", timeout=90_000)

            # If the UI doesn't use querystring params (or changes), we still at least get XHRs.
            # But we also try a direct navigation with params to encourage the right request.
            try:
                await page.goto(
                    f"{SEARCH_PAGE_URL}?base_query={params.get('base_query','')}"
                    f"&sort={params.get('sort','recent')}"
                    f"&offset={params.get('offset','0')}"
                    f"&result_limit={params.get('result_limit','25')}",
                    wait_until="networkidle",
                    timeout=90_000,
                )
            except Exception:
                pass

            await page.wait_for_timeout(6_000)
        finally:
            await browser.close()

    # Parse captured payloads
    seen: set[str] = set()
    for payload in api_payloads:
        positions = extract_positions(payload)
        for pos in positions:
            if not isinstance(pos, dict):
                continue
            j = normalize_job(pos)
            if not j:
                continue
            if j["id"] in seen:
                continue
            seen.add(j["id"])
            jobs.append(j)

    return jobs


async def get_latest_jobs() -> List[Dict[str, str]]:
    """
    Returns a list of jobs in the same shape as `scraper.py`:
      { id, title, location, link, found_at }
    """
    params = build_search_params()

    jobs = await _try_fetch_json(params)
    if jobs:
        return jobs

    # Fallback if JSON endpoint/params change.
    return await _try_intercept_from_page(params)


if __name__ == "__main__":
    found = asyncio.run(get_latest_jobs())
    print(f"\nTotal jobs found: {len(found)}")
    for j in found[:20]:
        print(f"- [{j['id']}] {j['title']} | {j['location']}")
        print(f"  Link: {j['link']}")
