import os
import sys
import tempfile
from typing import Optional

from git import GitCommandError, Repo
from halo import Halo
from pydriller import Commit, Repository


def clone_repo(repo_url: str) -> Optional[tempfile.TemporaryDirectory]:
    try:
        repo_temp_dir = tempfile.TemporaryDirectory()
        with Halo(text=f"Cloning from {repo_url}", enabled=sys.stdout.isatty()) as spinner:
            Repo.clone_from(repo_url, repo_temp_dir.name)
        return repo_temp_dir
    except GitCommandError:
        repo_temp_dir.cleanup()
        return None


def get_commit_from_repo_url(repo_url: str, rev_hash: str) -> Optional[Commit]:
    repo_temp_dir = clone_repo(repo_url)
    if repo_temp_dir is None:
        return None
    try:
        git_repo = Repository(repo_temp_dir.name, single=rev_hash)
        return next(git_repo.traverse_commits())
    except (ValueError, Exception):
        return None


def get_java_production_files_as_blobs(rev_commit: Commit, extension: str) -> list:
    java_prod_files_blobs = []
    for obj in rev_commit._c_object.tree.traverse():
        if getattr(obj, "type") != 'blob':  # 'blob' = file, 'tree' = directory
            continue
        if not f".{extension}" in os.fspath(getattr(obj, "path")):
            continue
        if "src/main" in os.fspath(getattr(obj, "path")):
            java_prod_files_blobs.append(obj)
    return java_prod_files_blobs


def blob_to_text(blob):
    try:
        blob_bytes = blob.data_stream.read() if blob is not None else None
        return blob_bytes.decode("utf-8", "ignore")
    except (AttributeError, ValueError):
        return None
