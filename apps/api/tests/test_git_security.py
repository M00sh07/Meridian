import pytest
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services.ingestion_job import is_safe_github_url, clone_repository, _git_svc
git_service = _git_svc

from unittest.mock import patch, MagicMock
from routers.repositories import create_repository
from schemas import RepositoryCreate
from fastapi import HTTPException

def test_is_safe_github_url_valid():
    valid_urls = [
        "https://github.com/octocat/Hello-World",
        "https://github.com/octocat/Hello-World.git",
        "https://github.com/M00sh07/Meridian",
        "https://github.com/M00sh07/Meridian.git/"
    ]
    for url in valid_urls:
        assert is_safe_github_url(url) is True, f"Valid URL was rejected: {url}"

def test_is_safe_github_url_invalid():
    invalid_urls = [
        "https://github.com.evil.com/a/b",
        "https://evil.com/a/b",
        "http://github.com/a/b",
        "https://user:pass@github.com/a/b",
        "https://github.com:8443/a/b",
        "https://github.com/a/b?x=1",
        "https://github.com/a/b#frag",
        "https://github.com/../../internal",
        "https://github.com/a/../b",
        "https://github.com/a/b/c",
        "https://github.com/@127.0.0.1/",
        "https://github.com\\@127.0.0.1/",
        "https://github.com/a/b with whitespace",
        "https://github.com/a/b\n--upload-pack=evil",
        "https://github.com/a",
        "https://github.com//b",
        "https://github.com/%2e%2e/b",
    ]
    for url in invalid_urls:
        assert is_safe_github_url(url) is False, f"Invalid URL was accepted: {url}"

@patch.object(git_service.git.Repo, 'clone_from')
def test_clone_repository_hardened(mock_clone_from):
    url = "https://github.com/owner/repo.git"
    dest = "/tmp/fake"
    clone_repository(url, dest)
    
    # Verify clone_from was called with proper options
    mock_clone_from.assert_called_once()
    kwargs = mock_clone_from.call_args.kwargs
    assert "env" in kwargs, "env missing in clone_from"
    env = kwargs["env"]
    assert env.get("GIT_CONFIG_COUNT") == "1"
    assert env.get("GIT_CONFIG_KEY_0") == "http.followRedirects"
    assert env.get("GIT_CONFIG_VALUE_0") == "false"
    
def test_router_rejects_invalid_url():
    # Setup mock dependencies
    mock_db = MagicMock()
    mock_bg_tasks = MagicMock()
    repo_in = RepositoryCreate(url="https://github.com/../../evil")
    
    with pytest.raises(HTTPException) as exc_info:
        create_repository(repo_in, mock_bg_tasks, mock_db)
        
    assert exc_info.value.status_code == 400
    assert "Only valid HTTPS GitHub URLs are supported" in exc_info.value.detail
