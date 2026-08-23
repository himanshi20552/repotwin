from pathlib import Path
import ast

IGNORED_DIRECTORIES = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    ".idea",
    ".vscode",
}


def get_python_files(root: Path) -> list[Path]:
    return [
        path
        for path in root.rglob("*.py")
        if not any(
            part in IGNORED_DIRECTORIES
            for part in path.parts
        )
    ]


def analyze_file(file_path: Path, root: Path):
    source = file_path.read_text(
        encoding="utf-8",
        errors="ignore",
    )

    try:
        tree = ast.parse(source)
    except SyntaxError:
        return [], []

    relative = file_path.relative_to(root)

    nodes = []
    edges = []

    file_id = f"file:{relative}"

    nodes.append({
        "id": file_id,
        "type": "file",
        "name": str(relative),
    })

    for node in tree.body:

        if isinstance(node, ast.ClassDef):

            class_id = f"class:{relative}:{node.name}"

            nodes.append({
                "id": class_id,
                "type": "class",
                "name": node.name,
                "file": str(relative),
                "line": node.lineno,
            })

            edges.append({
                "source": file_id,
                "target": class_id,
                "type": "contains",
            })

            for child in node.body:

                if isinstance(
                    child,
                    (ast.FunctionDef, ast.AsyncFunctionDef),
                ):

                    method_id = (
                        f"method:{relative}:"
                        f"{node.name}.{child.name}"
                    )

                    nodes.append({
                        "id": method_id,
                        "type": "method",
                        "name": child.name,
                        "class": node.name,
                        "file": str(relative),
                        "line": child.lineno,
                    })

                    edges.append({
                        "source": class_id,
                        "target": method_id,
                        "type": "contains",
                    })

        elif isinstance(
            node,
            (ast.FunctionDef, ast.AsyncFunctionDef),
        ):

            function_id = (
                f"function:{relative}:{node.name}"
            )

            nodes.append({
                "id": function_id,
                "type": "function",
                "name": node.name,
                "file": str(relative),
                "line": node.lineno,
            })

            edges.append({
                "source": file_id,
                "target": function_id,
                "type": "contains",
            })

    return nodes, edges


def build_typed_graph(repository_path: str) -> dict:
    root = Path(repository_path)

    all_nodes = []
    all_edges = []

    for file_path in get_python_files(root):

        nodes, edges = analyze_file(
            file_path,
            root,
        )

        all_nodes.extend(nodes)
        all_edges.extend(edges)

    return {
        "repository": root.name,
        "nodes": all_nodes,
        "edges": all_edges,
    }
