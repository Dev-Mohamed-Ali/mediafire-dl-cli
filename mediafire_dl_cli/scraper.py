from bs4 import BeautifulSoup
import requests
from .exceptions import ScraperError


def GetName(url: str) -> str:
    """Extract filename from a MediaFire URL."""
    return url.split('/')[-2]


def GetFileLink(url: str, session: requests.Session = None) -> str:
    """
    Scrape the direct download link from a MediaFire page URL.

    Args:
        url: MediaFire page URL (e.g. https://www.mediafire.com/file/abc123/myfile.zip)
        session: Optional requests.Session to reuse connections.

    Returns:
        Direct download URL string.

    Raises:
        ScraperError: If the download button is not found or the page is unreachable.
    """
    requester = session or requests
    try:
        response = requester.get(url, timeout=15)
        response.raise_for_status()
    except requests.RequestException as e:
        raise ScraperError(f"Failed to fetch page '{url}': {e}") from e

    soup = BeautifulSoup(response.content, "html.parser")
    btn = soup.find(id="downloadButton")
    if btn is None:
        raise ScraperError(
            f"Download button not found on '{url}'. "
            "The file may be removed, private, or the page structure has changed."
        )
    return btn.get("href")
