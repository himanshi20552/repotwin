from pathlib import Path
from git import Repo
import os
import shutil


def get_repositories_dir() -> Path:
    env_path = os.getenv("REPOSITORIES_DIR")
    if env_path:
        path = Path(env_path)
    elif Path("backend/data/repos").exists() or Path("backend").exists():
        path = Path("backend/data/repos")
    else:
        path = Path("data/repos")
    path.mkdir(parents=True, exist_ok=True)
    return path


def clone_repository(
    repository_url: str,
    repository_name: str,
    force_fresh: bool = False,
) -> Path:
    repos_dir = get_repositories_dir()
    destination = repos_dir / repository_name

    if destination.exists():
        if force_fresh:
            shutil.rmtree(destination, ignore_errors=True)
            Repo.clone_from(repository_url, destination)
        else:
            try:
                # Validate existing repository
                Repo(destination)
            except Exception:
                shutil.rmtree(destination, ignore_errors=True)
                Repo.clone_from(repository_url, destination)
    else:
        Repo.clone_from(repository_url, destination)

    return destination
