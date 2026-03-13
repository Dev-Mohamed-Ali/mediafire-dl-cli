from .downloader import Download, BulkDownload
from .scraper import GetFileLink, GetName
from .utils import AsMegabytes, GetFileSize

__all__ = ["Download", "BulkDownload", "GetFileLink", "GetName", "AsMegabytes", "GetFileSize"]
__version__ = "1.1.0"
