class MediaFireError(Exception):
    """Base exception for the mediafire_dl_cli package."""


class ScraperError(MediaFireError):
    """Raised when the direct download link cannot be extracted."""


class DownloadError(MediaFireError):
    """Raised when a download fails and cannot be resumed."""


class RangeNotSupportedError(DownloadError):
    """Raised when the server does not support HTTP Range requests (resume impossible)."""
