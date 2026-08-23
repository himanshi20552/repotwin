import ast
from pathlib import Path
from typing import Any

IGNORED_DIRECTORIES = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    ".idea",
    ".vscode",
    "build",
    "dist",
    ".egg-info",
}


def get_python_files(root: Path) -> list[Path]:
    return [
        path
        for path in root.rglob("*.py")
        if not any(part in IGNORED_DIRECTORIES for part in path.parts)
    ]


def extract_entity_code(lines: list[str], start_line: int, end_line: int | None) -> str:
    if not lines:
        return ""
    start_idx = max(0, start_line - 1)
    if end_line is not None and end_line >= start_line:
        end_idx = min(len(lines), end_line)
        return "\n".join(lines[start_idx:end_idx])
    return lines[start_idx] if start_idx < len(lines) else ""


def chunk_python_file(
    file_path: Path,
    root: Path,
    repository_name: str = "",
) -> list[dict[str, Any]]:
    relative = file_path.relative_to(root).as_posix()
    try:
        source_text = file_path.read_text(encoding="utf-8", errors="ignore")
        tree = ast.parse(source_text)
    except Exception:
        return []

    lines = source_text.splitlines()
    chunks: list[dict[str, Any]] = []

    # 1. Module-level overview chunk if docstring exists
    module_doc = ast.get_docstring(tree) or ""
    if module_doc:
        module_id = f"module:{relative}"
        chunks.append({
            "chunk_id": f"chunk:{module_id}",
            "entity_id": module_id,
            "type": "module",
            "name": relative,
            "file": relative,
            "start_line": 1,
            "end_line": min(len(lines), 30),
            "docstring": module_doc,
            "source_code": module_doc,
            "text": (
                f"Repository: {repository_name}\n"
                f"File: {relative}\n"
                f"Type: module\n"
                f"Module: {relative}\n"
                f"Docstring: {module_doc}"
            ),
            "metadata": {
                "repository": repository_name,
                "file": relative,
                "entity_id": module_id,
                "type": "module",
                "name": relative,
                "start_line": 1,
                "end_line": min(len(lines), 30),
            },
        })

    # 2. Extract Classes, Methods, and Functions
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            class_id = f"class:{relative}:{node.name}"
            class_doc = ast.get_docstring(node) or ""
            class_start = getattr(node, "lineno", 1)
            class_end = getattr(node, "end_lineno", class_start)
            class_code = extract_entity_code(lines, class_start, class_end)

            chunks.append({
                "chunk_id": f"chunk:{class_id}",
                "entity_id": class_id,
                "type": "class",
                "name": node.name,
                "file": relative,
                "start_line": class_start,
                "end_line": class_end,
                "docstring": class_doc,
                "source_code": class_code,
                "text": (
                    f"Repository: {repository_name}\n"
                    f"File: {relative}\n"
                    f"Type: class\n"
                    f"Class: {node.name}\n"
                    f"Lines: {class_start}-{class_end}\n"
                    f"Docstring: {class_doc}\n"
                    f"Code:\n{class_code[:1200]}"
                ),
                "metadata": {
                    "repository": repository_name,
                    "file": relative,
                    "entity_id": class_id,
                    "type": "class",
                    "name": node.name,
                    "start_line": class_start,
                    "end_line": class_end,
                },
            })

            # Methods inside class
            for child in node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    method_name = f"{node.name}.{child.name}"
                    method_id = f"method:{relative}:{method_name}"
                    method_doc = ast.get_docstring(child) or ""
                    method_start = getattr(child, "lineno", class_start)
                    method_end = getattr(child, "end_lineno", method_start)
                    method_code = extract_entity_code(lines, method_start, method_end)

                    chunks.append({
                        "chunk_id": f"chunk:{method_id}",
                        "entity_id": method_id,
                        "type": "method",
                        "name": method_name,
                        "file": relative,
                        "start_line": method_start,
                        "end_line": method_end,
                        "docstring": method_doc,
                        "source_code": method_code,
                        "text": (
                            f"Repository: {repository_name}\n"
                            f"File: {relative}\n"
                            f"Type: method\n"
                            f"Method: {method_name}\n"
                            f"Class: {node.name}\n"
                            f"Lines: {method_start}-{method_end}\n"
                            f"Docstring: {method_doc}\n"
                            f"Code:\n{method_code[:1500]}"
                        ),
                        "metadata": {
                            "repository": repository_name,
                            "file": relative,
                            "entity_id": method_id,
                            "type": "method",
                            "name": method_name,
                            "start_line": method_start,
                            "end_line": method_end,
                        },
                    })

        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            func_id = f"function:{relative}:{node.name}"
            func_doc = ast.get_docstring(node) or ""
            func_start = getattr(node, "lineno", 1)
            func_end = getattr(node, "end_lineno", func_start)
            func_code = extract_entity_code(lines, func_start, func_end)

            chunks.append({
                "chunk_id": f"chunk:{func_id}",
                "entity_id": func_id,
                "type": "function",
                "name": node.name,
                "file": relative,
                "start_line": func_start,
                "end_line": func_end,
                "docstring": func_doc,
                "source_code": func_code,
                "text": (
                    f"Repository: {repository_name}\n"
                    f"File: {relative}\n"
                    f"Type: function\n"
                    f"Function: {node.name}\n"
                    f"Lines: {func_start}-{func_end}\n"
                    f"Docstring: {func_doc}\n"
                    f"Code:\n{func_code[:1500]}"
                ),
                "metadata": {
                    "repository": repository_name,
                    "file": relative,
                    "entity_id": func_id,
                    "type": "function",
                    "name": node.name,
                    "start_line": func_start,
                    "end_line": func_end,
                },
            })

    return chunks


def chunk_repository(repository_path: str, repository_name: str = "") -> list[dict[str, Any]]:
    root = Path(repository_path)
    if not repository_name:
        repository_name = root.name

    all_chunks: list[dict[str, Any]] = []
    for file_path in get_python_files(root):
        file_chunks = chunk_python_file(file_path, root, repository_name)
        all_chunks.extend(file_chunks)

    return all_chunks
