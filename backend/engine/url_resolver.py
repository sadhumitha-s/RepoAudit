"""
URL Resolution Engine.

Resolves paper URLs (arXiv, PapersWithCode, Conferences) to Git repositories.
"""

from __future__ import annotations
import re
import logging
import httpx

logger = logging.getLogger(__name__)

_GITHUB_REPO_REGEX = re.compile(
    r"https?://(?:www\.)?github\.com/([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)",
    re.IGNORECASE
)

# Common GitHub paths that are not repositories
_IGNORED_OWNERS = {
    "login", "features", "pricing", "blog", "explore", "topics", "trending",
    "collections", "events", "sponsors", "about", "contact", "join", "enterprise",
    "team", "nonprofit", "security", "customer-stories", "readme"
}

def resolve_url(url: str) -> str:
    """
    Takes an input URL.
    - If it's a known Git repository URL (e.g., github.com), returns it.
    - If it's a paper URL (arxiv, paperswithcode, proceedings), attempts to 
      fetch the page and scrape the first valid GitHub repository link.
    - If resolution fails, raises ValueError.
    """
    url = url.strip()
    
    # 1. Check if it's already a direct GitHub repository URL
    match = _GITHUB_REPO_REGEX.search(url)
    if match:
        owner_repo = match.group(1).removesuffix("/").removesuffix(".git")
        owner = owner_repo.split('/')[0].lower()
        if owner not in _IGNORED_OWNERS and "/" in owner_repo:
            return f"https://github.com/{owner_repo}"
            
    # 2. Check if we should scrape this URL for code links
    scrape_domains = ["arxiv.org", "paperswithcode.com", "neurips.cc", "icml.cc", "iclr.cc", "cvf.com", "thecvf.com", "aclweb.org"]
    
    # Auto-prepend https:// if the user provided just the domain
    if any(url.lower().startswith(domain) for domain in scrape_domains):
        url = "https://" + url
        
    if not any(domain in url.lower() for domain in scrape_domains):
        # Unrecognized domain and not a direct GitHub link; 
        # return as is, let the git cloner fail if it's not a real git repo.
        return url

    # 3. Scrape the URL
    try:
        with httpx.Client(timeout=10.0, follow_redirects=True) as client:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            }
            
            # Additional logic for arXiv URLs: try to query HuggingFace Papers API
            arxiv_match = re.search(r"arxiv\.org/(?:abs|pdf|html)/(\d+\.\d+(?:v\d+)?)", url)
            if arxiv_match:
                arxiv_id = arxiv_match.group(1)
                hf_url = f"https://huggingface.co/api/papers/{arxiv_id}"
                try:
                    hf_resp = client.get(hf_url, headers=headers)
                    if hf_resp.status_code == 200:
                        matches = _GITHUB_REPO_REGEX.findall(hf_resp.text)
                        for owner_repo_match in matches:
                            owner_repo = owner_repo_match.removesuffix("/").removesuffix(".git")
                            if "/" not in owner_repo:
                                continue
                            owner = owner_repo.split('/')[0]
                            if owner.lower() not in _IGNORED_OWNERS:
                                resolved = f"https://github.com/{owner_repo}"
                                logger.info("Resolved arXiv URL %s via HF API -> %s", url, resolved)
                                return resolved
                except httpx.RequestError as e:
                    logger.debug("HF API fallback for arXiv failed: %s", e)
            
            # General scraping fallback
            resp = client.get(url, headers=headers)
            resp.raise_for_status()
            
            # Find all GitHub links in the HTML
            matches = _GITHUB_REPO_REGEX.findall(resp.text)
            
            for owner_repo_match in matches:
                owner_repo = owner_repo_match.removesuffix("/").removesuffix(".git")
                if "/" not in owner_repo:
                    continue
                owner = owner_repo.split('/')[0]
                if owner.lower() not in _IGNORED_OWNERS:
                    # Return the first valid repository found
                    resolved = f"https://github.com/{owner_repo}"
                    logger.info("Resolved paper URL %s -> %s", url, resolved)
                    return resolved
                    
            raise ValueError(f"Could not find any clear GitHub repository links on the page: {url}")
            
    except httpx.RequestError as e:
        logger.error("Failed to fetch %s for URL resolution: %s", url, e)
        raise ValueError(f"Failed to fetch the URL for resolution: {url} ({e})")
    except httpx.HTTPStatusError as e:
        logger.error("HTTP error while fetching %s: %s", url, e)
        raise ValueError(f"HTTP {e.response.status_code} error when resolving URL: {url}")
