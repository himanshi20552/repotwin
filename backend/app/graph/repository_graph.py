from pathlib import Path
import ast
import sys


IGNORED_DIRECTORIES = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    ".idea",
    ".vscode",
}


def get_python_files(repository_path: str) -> list[Path]:
    root = Path(repository_path)

    return [
        path
        for path in root.rglob("*.py")
        if not any(part in IGNORED_DIRECTORIES for part in path.parts)
    ]


def extract_imports(file_path: Path) -> list[str]:
    source = file_path.read_text(
        encoding="utf-8",
        errors="ignore",
    )

    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []

    imports = []

    for node in ast.walk(tree):

        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)

        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.append(node.module)

    return sorted(set(imports))


def get_internal_modules(root: Path, python_files: list[Path]) -> set[str]:
    modules = set()

    for file_path in python_files:
        relative = file_path.relative_to(root).as_posix()

        module = str(relative).rsplit(".", 1)[0].replace("/", ".")

        if module.endswith(".__init__"):
            module = module[:-9]

        modules.add(module)

    return modules


def classify_import(import_name: str, internal_modules: set[str]) -> str:
    import_root = import_name.split(".")[0]

    # Internal repository module
    for module in internal_modules:
        module_root = module.split(".")[0]

        if import_name == module or import_name.startswith(module + "."):
            return "internal"

        if import_root == module_root:
            return "internal"

    # Python standard library
    if import_root in sys.stdlib_module_names:
        return "standard_library"

    # Everything else is treated as external
    return "external"


def build_repository_graph(repository_path: str) -> dict:
    root = Path(repository_path)

    python_files = get_python_files(repository_path)

    internal_modules = get_internal_modules(
        root,
        python_files,
    )

    nodes = []
    edges = []

    for file_path in python_files:

        relative_posix = file_path.relative_to(root).as_posix()

        nodes.append({
            "id": relative_posix,
            "type": "file",
            "language": "Python",
        })

        imports = extract_imports(file_path)

        for imported_module in imports:

            dependency_type = classify_import(
                imported_module,
                internal_modules,
            )

            edges.append({
                "source": relative_posix,
                "target": imported_module,
                "type": "imports",
                "dependency": dependency_type,
            })

    return {
        "repository": root.name,
        "nodes": nodes,
        "edges": edges,
    }
