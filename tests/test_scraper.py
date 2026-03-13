import pytest
import responses
from mediafire_dl_cli.scraper import GetFileLink, GetName
from mediafire_dl_cli.exceptions import ScraperError

def test_get_name():
    assert GetName("https://www.mediafire.com/file/abc123/video.mp4") == "video.mp4"
    assert GetName("https://www.mediafire.com/file/xyz/archive.zip/") == "archive.zip"

@responses.activate
def test_get_file_link_success():
    url = "https://www.mediafire.com/file/test"
    mock_html = '<html><body><a id="downloadButton" href="https://download123.mediafire.com/direct.mp4">Download</a></body></html>'
    responses.add(responses.GET, url, body=mock_html, status=200)
    
    link = GetFileLink(url)
    assert link == "https://download123.mediafire.com/direct.mp4"

@responses.activate
def test_get_file_link_not_found():
    url = "https://www.mediafire.com/file/missing"
    mock_html = '<html><body><div>No button here</div></body></html>'
    responses.add(responses.GET, url, body=mock_html, status=200)
    
    with pytest.raises(ScraperError, match="Download button not found"):
        GetFileLink(url)

@responses.activate
def test_get_file_link_http_error():
    url = "https://www.mediafire.com/file/error"
    responses.add(responses.GET, url, status=404)
    
    with pytest.raises(ScraperError, match="Failed to fetch page"):
        GetFileLink(url)
