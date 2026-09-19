import os
import shutil
import tempfile
import git
from typing import List, Optional
from pydantic import HttpUrl

def validate_github_url(url: str) -> bool:
    return url.startswith("https://github.com/") and len(url.split("/")) >= 4

def clone_repository(url: str, dest_dir: str):
    """Shallow clone a repository."""
    git.Repo.clone_from(url, dest_dir, depth=1)

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
