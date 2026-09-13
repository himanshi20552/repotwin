"""Prepare the fixed repository used by the Week 4 evaluation."""

import subprocess
from pathlib import Path


REPO_URL = "https://github.com/fastapi/fastapi.git"
REPO_COMMIT = "c3f316b7e814667e8ee81e03a7330d00ee61e45c"


def ensure_evaluation_repo(repo_path: Path) -> None:
    """Clone and pin the evaluation repository if it is missing."""
    repo_path = Path(repo_path)

    if (repo_path / ".git").exists():
        current = subprocess.run(
            [
                "git",
                "-C",
                str(repo_path),
                "rev-parse",
                "HEAD",
            ],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()

        if current == REPO_COMMIT:
            print(f"Evaluation repository ready: {REPO_COMMIT}")
            return

        print(
            f"Repository exists at {current}; "
            f"switching to {REPO_COMMIT}"
        )

        subprocess.run(
            [
                "git",
                "-C",
                str(repo_path),
                "fetch",
                "--depth",
                "1",
                "origin",
                REPO_COMMIT,
            ],
            check=True,
        )

        subprocess.run(
            [
                "git",
                "-C",
                str(repo_path),
                "checkout",
                "--detach",
                REPO_COMMIT,
            ],
            check=True,
        )

        return

    repo_path.parent.mkdir(parents=True, exist_ok=True)

    print("Evaluation repository not found.")
    print("Cloning FastAPI repository...")

    subprocess.run(
        [
            "git",
            "clone",
            "--filter=blob:none",
            REPO_URL,
            str(repo_path),
        ],
        check=True,
    )

    subprocess.run(
        [
            "git",
            "-C",
            str(repo_path),
            "checkout",
            "--detach",
            REPO_COMMIT,
        ],
        check=True,
    )

    print(f"Evaluation repository ready: {REPO_COMMIT}")
