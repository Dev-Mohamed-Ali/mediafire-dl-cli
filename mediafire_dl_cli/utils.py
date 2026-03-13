import requests
from .scraper import GetFileLink
from .exceptions import DownloadError


def AsMegabytes(bytes_: int) -> float:
    """Convert bytes to megabytes, rounded to 2 decimal places."""
    return round(bytes_ / 1024 / 1024, 2)


def GetFileSize(url: str, session: requests.Session = None) -> int:
    """
    Return the content-length (in bytes) of the file behind a MediaFire page URL.

    Args:
        url: MediaFire page URL.
        session: Optional requests.Session.

    Returns:
        File size in bytes, or -1 if the server does not advertise it.
    """
    requester = session or requests
    direct = GetFileLink(url, session=session)
    try:
        with requester.head(direct, allow_redirects=True, timeout=15) as r:
            r.raise_for_status()
            return int(r.headers.get("content-length", -1))
    except requests.RequestException as e:
        raise DownloadError(f"Could not retrieve file size for '{url}': {e}") from e


def SupportsRanges(url: str, session: requests.Session = None) -> bool:
    """Check whether the server accepts HTTP Range requests for *url*."""
    requester = session or requests
    try:
        r = requester.head(url, allow_redirects=True, timeout=15)
        return r.headers.get("accept-ranges", "none").lower() != "none"
    except requests.RequestException:
        return False
