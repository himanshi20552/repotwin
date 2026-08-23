from pathlib import Path
from git import Repo
import shutil


REPOSITORIES_DIR = Path("data/repos")


def clone_repository(repository_url: str, repository_name: str) -> Path:
    REPOSITORIES_DIR.mkdir(parents=True, exist_ok=True)

    destination = REPOSITORIES_DIR / repository_name

    if destination.exists():
        shutil.rmtree(destination)

    Repo.clone_from(repository_url, destination)

    return destination
