from pathlib import Path

from app.graph.repository_graph import build_repository_graph
from app.graph.call_graph import build_call_graph
from app.analyzers.python_analyzer import analyze_python_file


def build_repository_twin(repository_path: str) -> dict:
    root = Path(repository_path)

    dependency_graph = build_repository_graph(
        repository_path
    )

    call_graph = build_call_graph(
        repository_path
    )

    entities = []

    for file_path in root.rglob("*.py"):

        if any(
            part in {
                ".git",
                ".venv",
                "venv",
                "node_modules",
                "__pycache__",
                ".idea",
                ".vscode",
            }
            for part in file_path.parts
        ):
            continue

        analysis = analyze_python_file(
            str(file_path)
        )

        relative_path = file_path.relative_to(root)

        for function in analysis["functions"]:
            entities.append({
                "id": f"{relative_path}:{function['name']}",
                "type": "function",
                "file": str(relative_path),
                "name": function["name"],
                "line": function["line"],
            })

        for class_info in analysis["classes"]:

            class_id = (
                f"{relative_path}:{class_info['name']}"
            )

            entities.append({
                "id": class_id,
                "type": "class",
                "file": str(relative_path),
                "name": class_info["name"],
                "line": class_info["line"],
            })

            for method in class_info["methods"]:

                entities.append({
                    "id": (
                        f"{relative_path}:"
                        f"{class_info['name']}."
                        f"{method['name']}"
                    ),
                    "type": "method",
                    "file": str(relative_path),
                    "class": class_info["name"],
                    "name": method["name"],
                    "line": method["line"],
                })

    return {
        "repository": root.name,
        "entities": entities,
        "dependency_graph": dependency_graph,
        "call_graph": call_graph,
    }
