from pathlib import Path
from collections import Counter


EXTENSION_LANGUAGE_MAP = {
    ".py": "Python",
    ".js": "JavaScript",
    ".jsx": "JavaScript",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".java": "Java",
    ".c": "C",
    ".cpp": "C++",
    ".h": "C/C++",
    ".cs": "C#",
    ".go": "Go",
    ".rs": "Rust",
    ".php": "PHP",
    ".rb": "Ruby",
    ".html": "HTML",
    ".css": "CSS",
    ".scss": "SCSS",
    ".sql": "SQL",
}


IGNORED_DIRECTORIES = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    ".idea",
    ".vscode",
    "dist",
    "build",
}


def analyze_repository(repository_path: str) -> dict:
    root = Path(repository_path)

    files = []
    languages = Counter()

    for path in root.rglob("*"):
        if not path.is_file():
            continue

        if any(part in IGNORED_DIRECTORIES for part in path.parts):
            continue

        files.append(str(path.relative_to(root)))

        language = EXTENSION_LANGUAGE_MAP.get(path.suffix.lower())

        if language:
            languages[language] += 1

    return {
        "repository": root.name,
        "file_count": len(files),
        "languages": dict(languages),
        "files": files[:200],
    }
