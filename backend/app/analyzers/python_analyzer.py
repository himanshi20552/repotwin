import ast
from pathlib import Path


def analyze_python_file(file_path: str) -> dict:
    path = Path(file_path)

    source = path.read_text(encoding="utf-8", errors="ignore")
    tree = ast.parse(source)

    imports = []
    functions = []
    classes = []

    for node in ast.iter_child_nodes(tree):

        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)

        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.append(node.module)

        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            functions.append({
                "name": node.name,
                "line": node.lineno,
                "type": (
                    "async_function"
                    if isinstance(node, ast.AsyncFunctionDef)
                    else "function"
                ),
            })

        elif isinstance(node, ast.ClassDef):
            class_info = {
                "name": node.name,
                "line": node.lineno,
                "methods": [],
            }

            for child in node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    class_info["methods"].append({
                        "name": child.name,
                        "line": child.lineno,
                        "type": (
                            "async_method"
                            if isinstance(child, ast.AsyncFunctionDef)
                            else "method"
                        ),
                    })

            classes.append(class_info)

    return {
        "file": str(path),
        "language": "Python",
        "imports": sorted(set(imports)),
        "functions": functions,
        "classes": classes,
    }
