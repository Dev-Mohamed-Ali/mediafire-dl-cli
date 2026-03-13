# mediafire-dl-cli

A robust MediaFire downloader with:

- ✅ **Auto-resume** — interrupted downloads pick up where they left off via HTTP Range requests + `.part` files
- ✅ **Custom headers** — pass any HTTP headers (cookies, auth, referer, …)
- ✅ **Retries + back-off** — configurable retry count with exponential back-off on transient errors
- ✅ **Rich progress bar** — speed (MB/s), ETA, percent, downloaded/total
- ✅ **Bulk/parallel download** — thread-pool with configurable worker count
- ✅ **CLI** — use straight from the terminal
- ✅ **Callback hook** — `on_progress` for GUI or logging integration

---

## Install

```bash
pip install mediafire-dl-cli
# or for local development:
pip install -e .
```

---

## Python API

### Single file

```python
from mediafire_dl_cli import Download

path = Download(
    url="https://www.mediafire.com/file/abc123/myarchive.zip",
    output="/home/user/downloads",   # optional, defaults to script dir
    filename="renamed.zip",          # optional
    headers={"Cookie": "session=xyz"},  # optional extra headers
    chunk_size=64 * 1024,            # 64 KB (default)
    retries=5,                       # HTTP-level retries (default 5)
    backoff=1.0,                     # exponential back-off factor
    show_progress=True,
    on_progress=lambda done, total: None,  # optional callback
)
print(f"Saved to {path}")
```

#### Auto-resume behaviour

If the download is interrupted (Ctrl-C, crash, network drop), a `.part` file is kept on disk.  
Calling `Download()` again with the **same arguments** will automatically resume from the byte offset where it stopped — as long as the server supports `Accept-Ranges`.

If the server does **not** support range requests, a `RangeNotSupportedError` is raised.  
Delete the `.part` file manually and start over in that case.

---

### Bulk download

```python
from mediafire_dl_cli import BulkDownload

urls = [
    "https://www.mediafire.com/file/abc/file1.zip",
    "https://www.mediafire.com/file/def/file2.zip",
    "https://www.mediafire.com/file/ghi/file3.zip",
]

results = BulkDownload(
    urls,
    output="/home/user/downloads",
    headers={"Referer": "https://example.com"},
    max_workers=3,   # parallel downloads
    retries=5,
    show_progress=True,
)

# results: {url: "/path/to/file" | Exception}
for url, result in results.items():
    if isinstance(result, Exception):
        print(f"FAILED  {url}: {result}")
    else:
        print(f"OK      {result}")
```

---

## CLI Examples

### Single file download
```bash
# Simple download to current directory
mediafire-dl-cli https://www.mediafire.com/file/abc123/video.mp4

# Download to specific directory with custom filename (filename inferred from URL if not provided)
mediafire-dl-cli https://www.mediafire.com/file/abc123/video.mp4 -o ~/Downloads
```

### Bulk download (Parallel)
```bash
# Download multiple URLs using 5 parallel workers
mediafire-dl-cli url1 url2 url3 url4 url5 -w 5 -o ./my_collection
```

### Advanced Usage
```bash
# Custom headers (useful for auth/sessions)
mediafire-dl-cli <url> -H "Cookie: session=abc" -H "User-Agent: MyDownloader/1.0"

# More retries for unstable connections (default is 5)
mediafire-dl-cli <url> -r 20

# Suppress progress bar (useful for cron jobs or logging)
mediafire-dl-cli <url> --no-progress
```

---

## Exceptions

| Exception | When |
|---|---|
| `ScraperError` | Download button not found / page unreachable |
| `DownloadError` | HTTP or I/O error during transfer |
| `RangeNotSupportedError` | Resume attempted but server rejects Range header |

All inherit from `MediaFireError` for easy broad catching:

```python
from mediafire_dl_cli.exceptions import MediaFireError
try:
    Download(url)
except MediaFireError as e:
    print(f"mediafire_dl_cli error: {e}")
```

---

## Package layout

```
mediafire-dl-cli/
├── mediafire_dl_cli/
│   ├── __init__.py       exports: Download, BulkDownload, GetFileLink, …
│   ├── __main__.py       CLI entry point
│   ├── downloader.py     core download logic
│   ├── scraper.py        HTML scraping → direct link
│   ├── utils.py          helpers: AsMegabytes, GetFileSize, SupportsRanges
│   └── exceptions.py     custom exception hierarchy
├── pyproject.toml        modern packaging metadata
├── README.md             documentation
└── LICENSE               MIT license
```
