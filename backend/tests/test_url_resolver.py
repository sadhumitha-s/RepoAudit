from engine.url_resolver import resolve_url
import pytest
from unittest.mock import patch, MagicMock
from httpx import HTTPStatusError, RequestError

def test_github_url_pass_through():
    url = "https://github.com/huggingface/transformers"
    assert resolve_url(url) == url

def test_github_url_trailing_slash():
    assert resolve_url("https://github.com/foo/bar/") == "https://github.com/foo/bar"

def test_github_git_extension():
    assert resolve_url("https://github.com/foo/bar.git") == "https://github.com/foo/bar"

def test_github_rstrip_bug():
    # .rstrip(".git") would strip "git" from the end of the string!
    # "https://github.com/huggingface/git"
    assert resolve_url("https://github.com/huggingface/git") == "https://github.com/huggingface/git"
    assert resolve_url("https://github.com/facebook/target") == "https://github.com/facebook/target"

def test_github_url_with_fragments():
    url = "https://github.com/foo/bar/tree/main#readme"
    assert resolve_url(url) == "https://github.com/foo/bar"

@patch('engine.url_resolver.httpx.Client')
def test_missing_schema_prepend(mock_client_class):
    mock_client = MagicMock()
    mock_client_class.return_value.__enter__.return_value = mock_client
    
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = '{"githubUrls": ["https://github.com/meta-llama/llama-recipes"]}'
    mock_client.get.return_value = mock_resp
    
    # Missing https://
    url = "arxiv.org/abs/2312.11514"
    resolved = resolve_url(url)
    assert resolved == "https://github.com/meta-llama/llama-recipes"
    
    # Ensure the client was called with https://
    mock_client.get.assert_any_call("https://huggingface.co/api/papers/2312.11514", headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'})

@patch('engine.url_resolver.httpx.Client')
def test_arxiv_resolution(mock_client_class):
    # Mocking HF API fallback
    mock_client = MagicMock()
    mock_client_class.return_value.__enter__.return_value = mock_client
    
    # Mock HF API successful response containing github url
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = '{"githubUrls": ["https://github.com/meta-llama/llama-recipes"]}'
    mock_client.get.return_value = mock_resp
    
    url = "https://arxiv.org/abs/2312.11514"
    resolved = resolve_url(url)
    assert resolved == "https://github.com/meta-llama/llama-recipes"

@patch('engine.url_resolver.httpx.Client')
def test_papers_with_code_resolution(mock_client_class):
    mock_client = MagicMock()
    mock_client_class.return_value.__enter__.return_value = mock_client
    
    # Mock PWC page containing github url in HTML
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = '<a href="https://github.com/KaimingHe/deep-residual-networks">Code</a>'
    mock_client.get.return_value = mock_resp
    
    url = "https://paperswithcode.com/paper/deep-residual-learning-for-image-recognition"
    resolved = resolve_url(url)
    assert resolved == "https://github.com/KaimingHe/deep-residual-networks"

@patch('engine.url_resolver.httpx.Client')
def test_invalid_paper_url(mock_client_class):
    mock_client = MagicMock()
    mock_client_class.return_value.__enter__.return_value = mock_client
    
    # Simulate an HTTP error when fetching
    mock_resp = MagicMock()
    mock_resp.status_code = 404
    mock_resp.raise_for_status.side_effect = HTTPStatusError("404 Error", request=MagicMock(), response=mock_resp)
    mock_client.get.return_value = mock_resp
    
    url = "https://arxiv.org/abs/0000.00000"
    with pytest.raises(ValueError, match="HTTP 404 error"):
        resolve_url(url)

def test_unsupported_url_pass_through():
    # Testing that it returns the url itself if it's not a supported paper domain 
    # and not a recognized github URL. The Git cloner will later handle it.
    url = "https://gitlab.com/foo/bar"
    assert resolve_url(url) == url
