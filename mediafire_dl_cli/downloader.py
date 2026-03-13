"""
mediafire_dl_cli.downloader
~~~~~~~~~~~~~~~~~~~~~~~
Core download logic with:
  - Auto-resume on interruption (HTTP Range requests + .part file)
  - Custom request headers support
  - Configurable retries with exponential back-off
  - Rich progress display (speed, ETA, bar)
  - Thread-pool bulk downloading
"""

from __future__ import annotations

import os
import sys
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, Dict, List, Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .scraper import GetFileLink, GetName
from .utils import AsMegabytes, SupportsRanges
from .exceptions import DownloadError, RangeNotSupportedError

# ──────────────────────────────────────────────
# Internal helpers
# ──────────────────────────────────────────────

_PRINT_LOCK = threading.Lock()


def _make_session(
    retries: int = 5,
    backoff: float = 1.0,
    extra_headers: Optional[Dict[str, str]] = None,
) -> requests.Session:
    """Build a requests.Session with retry logic and optional extra headers."""
    session = requests.Session()

    retry_strategy = Retry(
        total=retries,
        backoff_factor=backoff,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["HEAD", "GET"],
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("https://", adapter)
    session.mount("http://", adapter)

    session.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0 Safari/537.36"
            )
        }
    )
    if extra_headers:
        session.headers.update(extra_headers)

    return session


def _format_speed(bytes_per_sec: float) -> str:
    if bytes_per_sec >= 1_048_576:
        return f"{bytes_per_sec / 1_048_576:.1f} MB/s"
    if bytes_per_sec >= 1024:
        return f"{bytes_per_sec / 1024:.1f} KB/s"
    return f"{bytes_per_sec:.0f} B/s"


def _format_eta(seconds: float) -> str:
    if seconds < 0 or seconds > 86400:
        return "--:--"
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h}h{m:02d}m{s:02d}s"
    return f"{m:02d}m{s:02d}s" if m else f"{s}s"


def _progress_bar(pct: int, width: int = 30) -> str:
    filled = int(width * pct / 100)
    return "[" + "█" * filled + "░" * (width - filled) + "]"


def _print_progress(
    filename: str,
    downloaded: int,
    total: int,
    speed: float,
    elapsed: float,
) -> None:
    if total > 0:
        pct = int(100 * downloaded / total)
        eta = (total - downloaded) / speed if speed > 0 else -1
        bar = _progress_bar(pct)
        line = (
            f"\r{bar} {pct:>3}%  "
            f"{AsMegabytes(downloaded)}/{AsMegabytes(total)} MB  "
            f"{_format_speed(speed)}  ETA {_format_eta(eta)}  [{filename}]"
        )
    else:
        line = (
            f"\r[{'?' * 30}]  ???%  "
            f"{AsMegabytes(downloaded)}/? MB  "
            f"{_format_speed(speed)}  [{filename}]"
        )
    with _PRINT_LOCK:
        sys.stdout.write(line)
        sys.stdout.flush()


# ──────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────


def Download(
    url: str,
    output: str = "",
    filename: str = "",
    headers: Optional[Dict[str, str]] = None,
    chunk_size: int = 1024 * 64,          # 64 KB
    retries: int = 5,
    backoff: float = 1.0,
    show_progress: bool = True,
    on_progress: Optional[Callable[[int, int], None]] = None,
) -> str:
    """
    Download a MediaFire file with auto-resume support.

    The download writes to ``<output>/<filename>.part`` and renames it to
    ``<output>/<filename>`` only on completion.  If the transfer is interrupted
    and you call Download() again with the same arguments, it will resume from
    where it left off (provided the server supports HTTP Range requests).

    Args:
        url:           MediaFire page URL.
        output:        Directory to save the file. Defaults to the script's directory.
        filename:      Override the detected filename.
        headers:       Extra HTTP headers to send with every request.
        chunk_size:    Bytes read per iteration (default 64 KB).
        retries:       Number of HTTP-level retries on transient errors.
        backoff:       Exponential back-off factor between retries (seconds).
        show_progress: Print a progress bar to stdout.
        on_progress:   Optional callback ``fn(downloaded_bytes, total_bytes)``
                       called after every chunk.

    Returns:
        Absolute path of the downloaded file.

    Raises:
        DownloadError: On unrecoverable HTTP or I/O errors.
        RangeNotSupportedError: If the server rejects a resume attempt.
    """
    session = _make_session(retries=retries, backoff=backoff, extra_headers=headers)

    if not filename:
        filename = GetName(url)
    if not output:
        output = os.path.dirname(os.path.realpath(__file__))

    os.makedirs(output, exist_ok=True)

    direct_url = GetFileLink(url, session=session)
    final_path = os.path.join(output, filename)
    part_path = final_path + ".part"

    # ── Determine resume offset ──────────────────
    resume_from = 0
    if os.path.exists(part_path):
        resume_from = os.path.getsize(part_path)

    req_headers: Dict[str, str] = {}
    if resume_from > 0:
        if not SupportsRanges(direct_url, session=session):
            raise RangeNotSupportedError(
                f"Server does not support Range requests; cannot resume '{filename}'. "
                "Delete the .part file to start over."
            )
        req_headers["Range"] = f"bytes={resume_from}-"

    # ── Stream download ──────────────────────────
    try:
        with session.get(
            direct_url, stream=True, headers=req_headers, timeout=30
        ) as r:
            if r.status_code == 416:
                # Requested range not satisfiable → file already complete
                os.rename(part_path, final_path)
                return final_path

            r.raise_for_status()

            content_length = int(r.headers.get("content-length", 0))
            total = resume_from + content_length if content_length else 0

            mode = "ab" if resume_from > 0 else "wb"
            downloaded = resume_from
            start_time = time.monotonic()
            last_time = start_time
            last_downloaded = downloaded

            with open(part_path, mode) as f:
                for chunk in r.iter_content(chunk_size=chunk_size):
                    if not chunk:
                        continue
                    f.write(chunk)
                    downloaded += len(chunk)

                    now = time.monotonic()
                    elapsed = now - last_time
                    if elapsed >= 0.5:          # update every 0.5 s
                        speed = (downloaded - last_downloaded) / elapsed
                        last_time = now
                        last_downloaded = downloaded
                        if show_progress:
                            _print_progress(
                                filename, downloaded, total, speed, now - start_time
                            )
                        if on_progress:
                            on_progress(downloaded, total)

        # Rename .part → final only on clean completion
        os.rename(part_path, final_path)
        if show_progress:
            with _PRINT_LOCK:
                sys.stdout.write(f"\r✔ {filename} — {AsMegabytes(downloaded)} MB downloaded.\n")
                sys.stdout.flush()

        return final_path

    except (requests.RequestException, OSError) as e:
        raise DownloadError(
            f"Download failed for '{filename}' (partial file kept at '{part_path}'): {e}"
        ) from e


def BulkDownload(
    urls: List[str],
    output: str = "",
    headers: Optional[Dict[str, str]] = None,
    max_workers: int = 3,
    retries: int = 5,
    backoff: float = 1.0,
    show_progress: bool = True,
) -> Dict[str, str | Exception]:
    """
    Download multiple MediaFire URLs concurrently.

    Args:
        urls:         List of MediaFire page URLs.
        output:       Directory to save files.
        headers:      Extra HTTP headers for every request.
        max_workers:  Number of parallel downloads (default 3).
        retries:      Per-file HTTP retry count.
        backoff:      Exponential back-off factor.
        show_progress: Print per-file progress bars.

    Returns:
        Dict mapping each URL to either its saved path (str) or the Exception
        that occurred.
    """
    total = len(urls)
    print(f"[Bulk download] {total} file(s) — up to {max_workers} in parallel\n")

    results: Dict[str, str | Exception] = {}

    def _worker(url: str) -> tuple[str, str | Exception]:
        try:
            path = Download(
                url,
                output=output,
                headers=headers,
                retries=retries,
                backoff=backoff,
                show_progress=show_progress,
            )
            return url, path
        except Exception as exc:
            return url, exc

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(_worker, u): u for u in urls}
        for future in as_completed(futures):
            url, result = future.result()
            results[url] = result
            if isinstance(result, Exception):
                with _PRINT_LOCK:
                    print(f"\n✘ FAILED  {url}\n  → {result}")

    success = sum(1 for v in results.values() if not isinstance(v, Exception))
    failed = total - success
    print(f"\n[Done] {success}/{total} succeeded, {failed} failed.")
    return results
