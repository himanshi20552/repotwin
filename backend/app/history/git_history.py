from pathlib import Path
import subprocess
from collections import Counter


def run_git(
    repository_path: str,
    args: list[str],
) -> str:

    result = subprocess.run(
        ["git", "-C", repository_path, *args],
        capture_output=True,
        text=True,
        check=False,
    )

    if result.returncode != 0:
        return ""

    return result.stdout


def file_history(
    repository_path: str,
    file_path: str,
    limit: int = 50,
) -> dict:

    output = run_git(
        repository_path,
        [
            "log",
            "--follow",
            f"--max-count={limit}",
            "--format=%H|%ad|%s",
            "--date=short",
            "--",
            file_path,
        ],
    )

    commits = []

    for line in output.splitlines():

        parts = line.split("|", 2)

        if len(parts) != 3:
            continue

        commits.append({
            "commit": parts[0],
            "date": parts[1],
            "message": parts[2],
        })

    return {
        "file": file_path,
        "commit_count": len(commits),
        "commits": commits,
    }


def co_changed_files(
    repository_path: str,
    file_path: str,
    limit: int = 50,
) -> list[dict]:

    output = run_git(
        repository_path,
        [
            "log",
            "--follow",
            f"--max-count={limit}",
            "--name-only",
            "--format=COMMIT:%H",
            "--",
            file_path,
        ],
    )

    counts = Counter()

    current_commit_files = []

    for line in output.splitlines():

        line = line.strip()

        if not line:
            continue

        if line.startswith("COMMIT:"):

            for changed_file in current_commit_files:

                if changed_file != file_path:
                    counts[changed_file] += 1

            current_commit_files = []
            continue

        current_commit_files.append(line)

    for changed_file in current_commit_files:

        if changed_file != file_path:
            counts[changed_file] += 1

    return [
        {
            "file": file,
            "co_change_count": count,
        }
        for file, count in counts.most_common(20)
    ]


def symbol_history(
    repository_path: str,
    file_path: str,
    symbol: str,
    limit: int = 50,
) -> dict:

    # Search for additions/deletions involving the symbol.
    output = run_git(
        repository_path,
        [
            "log",
            f"--max-count={limit}",
            "-S",
            symbol,
            "--format=%H|%ad|%s",
            "--date=short",
            "--",
            file_path,
        ],
    )

    commits = []

    for line in output.splitlines():

        parts = line.split("|", 2)

        if len(parts) != 3:
            continue

        commits.append({
            "commit": parts[0],
            "date": parts[1],
            "message": parts[2],
        })

    return {
        "file": file_path,
        "symbol": symbol,
        "commit_count": len(commits),
        "commits": commits,
    }


def analyze_history(
    repository_path: str,
    file_path: str,
    symbol: str | None = None,
) -> dict:

    result = {
        "file_history": file_history(
            repository_path,
            file_path,
        ),
        "co_changed_files": co_changed_files(
            repository_path,
            file_path,
        ),
    }

    if symbol:

        result["symbol_history"] = symbol_history(
            repository_path,
            file_path,
            symbol,
        )

    return result
