import os
import shutil
import tempfile
import git
import re
from urllib.parse import urlparse
from typing import List, Optional
from pydantic import HttpUrl


def is_safe_github_url(url: str) -> bool:
    try:
        # Prevent any whitespace injection
        if any(c.isspace() for c in url):
            return False

        # Parse the URL
        parsed = urlparse(url)

        # 1. Exact Scheme and Hostname
        if parsed.scheme != "https" or parsed.hostname != "github.com":
            return False

        # 2. No userinfo, ports, query, or fragments
        if parsed.username or parsed.password or parsed.port or parsed.query or parsed.fragment:
            return False

        # 3. Strict path structure: /owner/repo (optional .git, optional /)
        if not re.match(r"^/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+(?:\.git)?/?$", parsed.path):
            return False

        # 4. Reject encoded path traversals or malformed structures explicitly
        if ".." in parsed.path or "%" in parsed.path or "\\" in url:
            return False

        return True
    except ValueError: # Catch invalid ports during parsing
        return False
    except Exception:
        return False

def clone_repository(url: str, dest_dir: str):
    """Shallow clone a repository with strict SSRF mitigations."""
    env = os.environ.copy()
    env["GIT_CONFIG_COUNT"] = "1"
    env["GIT_CONFIG_KEY_0"] = "http.followRedirects"
    env["GIT_CONFIG_VALUE_0"] = "false"

    git.Repo.clone_from(url, dest_dir, env=env)


def _iter_commits(repository):
    try:
        return list(repository.iter_commits())
    except (ValueError, git.BadName):
        # A repository with no commits has an unborn HEAD, so iter_commits()
        # raises instead of yielding nothing. Treat that as empty history.
        return []


def extract_commits(repo_path: str):
    """Return commit metadata from a cloned repository."""
    repository = git.Repo(repo_path)
    return [
        {
            "sha": commit.hexsha,
            "author_name": commit.author.name,
            "author_email": commit.author.email,
            "message": commit.message,
            "committed_at": commit.committed_datetime,
        }
        for commit in _iter_commits(repository)
    ]


def extract_commits_with_changes(repo_path: str):
    """Return commit metadata and file changes from a cloned repository."""
    repository = git.Repo(repo_path)
    commits_data = []
    for commit in _iter_commits(repository):
        changes = []
        if commit.parents:
            # Compare with parent to get changed files
            diffs = commit.parents[0].diff(commit)
            for diff in diffs:
                # diff.change_type: A, M, D, R
                change_type = diff.change_type
                # Normalize types
                if change_type == 'A': change_type = 'added'
                elif change_type == 'M': change_type = 'modified'
                elif change_type == 'D': change_type = 'deleted'
                elif change_type == 'R': change_type = 'renamed'

                path = diff.b_path
                previous_path = diff.a_path if change_type == 'renamed' else None
                changes.append({"path": path, "previous_path": previous_path, "type": change_type})

        commits_data.append({
            "sha": commit.hexsha,
            "author_name": commit.author.name,
            "author_email": commit.author.email,
            "message": commit.message,
            "committed_at": commit.committed_datetime,
            "changes": changes
        })
    return commits_data


def discover_files(repo_path: str) -> List[str]:
    """Discover files, skipping unwanted directories and files."""
    skip_dirs = {'.git', 'node_modules', 'build', 'dist', 'vendor', '__pycache__', '.venv', 'venv'}
    skip_exts = {'.pyc', '.pyo', '.pyd', '.so', '.dll', '.dylib', '.exe', '.bin', '.png', '.jpg', '.jpeg', '.gif', '.ico', '.svg', '.mp4', '.mp3', '.zip', '.tar', '.gz'}
    max_file_size = 1024 * 1024 # 1 MB

    discovered = []
    for root, dirs, files in os.walk(repo_path):
        dirs[:] = [d for d in dirs if d not in skip_dirs]
        for file in files:
            ext = os.path.splitext(file)[1].lower()
            if ext in skip_exts:
                continue
            file_path = os.path.join(root, file)
            if os.path.getsize(file_path) > max_file_size:
                continue
            discovered.append(os.path.relpath(file_path, repo_path))
    return discovered
