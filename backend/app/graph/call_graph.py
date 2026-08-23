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


def get_attribute_name(node):
    if isinstance(node, ast.Name):
        return node.id

    if isinstance(node, ast.Attribute):
        return node.attr

    return None


def get_attribute_root(node):
    if isinstance(node, ast.Name):
        return node.id

    if isinstance(node, ast.Attribute):
        return get_attribute_root(node.value)

    return None


def extract_definitions(
    file_path: Path,
    root: Path,
) -> dict:

    source = file_path.read_text(
        encoding="utf-8",
        errors="ignore",
    )

    try:
        tree = ast.parse(source)
    except SyntaxError:
        return {}

    relative_path = file_path.relative_to(root)

    definitions = {}

    for node in tree.body:

        if isinstance(
            node,
            (ast.FunctionDef, ast.AsyncFunctionDef),
        ):

            definitions.setdefault(
                node.name,
                []
            ).append({
                "id": (
                    f"function:{relative_path}:"
                    f"{node.name}"
                ),
                "type": "function",
                "class": None,
            })

        elif isinstance(node, ast.ClassDef):

            for child in node.body:

                if isinstance(
                    child,
                    (ast.FunctionDef, ast.AsyncFunctionDef),
                ):

                    definitions.setdefault(
                        child.name,
                        []
                    ).append({
                        "id": (
                            f"method:{relative_path}:"
                            f"{node.name}.{child.name}"
                        ),
                        "type": "method",
                        "class": node.name,
                    })

    return definitions


def build_class_method_table(
    python_files: list[Path],
    root: Path,
) -> dict:

    table = {}

    for file_path in python_files:

        source = file_path.read_text(
            encoding="utf-8",
            errors="ignore",
        )

        try:
            tree = ast.parse(source)
        except SyntaxError:
            continue

        relative_path = file_path.relative_to(root)

        for node in tree.body:

            if not isinstance(node, ast.ClassDef):
                continue

            for child in node.body:

                if isinstance(
                    child,
                    (ast.FunctionDef, ast.AsyncFunctionDef),
                ):

                    key = (
                        node.name,
                        child.name,
                    )

                    table.setdefault(
                        key,
                        []
                    ).append(
                        f"method:{relative_path}:"
                        f"{node.name}.{child.name}"
                    )

    return table



def build_class_inheritance_table(
    python_files: list[Path],
    root: Path,
) -> dict:
    """
    Build a mapping of class -> base classes.

    Example:
        Session -> ["SessionRedirectMixin"]
    """

    table = {}

    for file_path in python_files:

        source = file_path.read_text(
            encoding="utf-8",
            errors="ignore",
        )

        try:
            tree = ast.parse(source)
        except SyntaxError:
            continue

        for node in tree.body:

            if not isinstance(node, ast.ClassDef):
                continue

            bases = []

            for base in node.bases:

                if isinstance(base, ast.Name):
                    bases.append(base.id)

                elif isinstance(base, ast.Attribute):
                    bases.append(base.attr)

            table[node.name] = bases

    return table


def find_class_method(
    class_name: str,
    method_name: str,
    class_method_table: dict,
    inheritance_table: dict,
    visited: set | None = None,
):
    """
    Find a method on a class or one of its base classes.
    """

    if visited is None:
        visited = set()

    if class_name in visited:
        return []

    visited.add(class_name)

    candidates = class_method_table.get(
        (class_name, method_name),
        [],
    )

    if candidates:
        return candidates

    for base_class in inheritance_table.get(
        class_name,
        [],
    ):

        candidates = find_class_method(
            base_class,
            method_name,
            class_method_table,
            inheritance_table,
            visited,
        )

        if candidates:
            return candidates

    return []

def extract_import_aliases(tree):
    aliases = {}

    for node in tree.body:

        if isinstance(node, ast.ImportFrom):

            if node.module:
                for alias in node.names:

                    local_name = (
                        alias.asname
                        or alias.name
                    )

                    aliases[local_name] = (
                        node.module,
                        alias.name,
                    )

        elif isinstance(node, ast.Import):

            for alias in node.names:

                local_name = (
                    alias.asname
                    or alias.name.split(".")[0]
                )

                aliases[local_name] = (
                    alias.name,
                    None,
                )

    return aliases


def get_called_class_name(node, import_aliases):
    """
    Infer the class name created by a constructor call.

    Supported examples:

        Session()
        requests.Session()
        rq.Session()

    Returns None when the type cannot be safely inferred.
    """

    if not isinstance(node, ast.Call):
        return None

    func = node.func

    # Session()
    if isinstance(func, ast.Name):
        return func.id

    # requests.Session()
    # rq.Session()
    if isinstance(func, ast.Attribute):

        method_name = func.attr

        if isinstance(func.value, ast.Name):

            root = func.value.id

            # If the root is an imported module, the final
            # attribute is the class name.
            if root in import_aliases:
                return method_name

            # We can still conservatively treat a capitalized
            # attribute as a possible constructor.
            if method_name[:1].isupper():
                return method_name

    return None


def extract_local_types(
    function_node,
    import_aliases,
):
    """
    Infer simple local variable types.

    Supported examples:

        resp: Response
        resp = Response()
        ses = requests.Session()
        s = requests.Session()
    """

    types = {}

    # ---------------------------------------------------------
    # Function argument annotations
    # ---------------------------------------------------------

    arguments = list(
        function_node.args.args
    )

    for argument in arguments:

        if not argument.annotation:
            continue

        annotation = argument.annotation

        if isinstance(
            annotation,
            ast.Name,
        ):

            types[argument.arg] = (
                annotation.id
            )

        elif isinstance(
            annotation,
            ast.Subscript,
        ):

            slice_node = annotation.slice

            if isinstance(
                slice_node,
                ast.Name,
            ):

                types[argument.arg] = (
                    slice_node.id
                )

            elif (
                isinstance(
                    slice_node,
                    ast.Tuple,
                )
                and slice_node.elts
            ):

                first = slice_node.elts[0]

                if isinstance(
                    first,
                    ast.Name,
                ):

                    types[argument.arg] = (
                        first.id
                    )

    # ---------------------------------------------------------
    # Local assignments
    #
    # Examples:
    #
    #   response = Response()
    #   session = requests.Session()
    # ---------------------------------------------------------

    for node in ast.walk(function_node):

        if not isinstance(
            node,
            ast.Assign,
        ):
            continue

        if not isinstance(
            node.value,
            ast.Call,
        ):
            continue

        class_name = get_called_class_name(
            node.value,
            import_aliases,
        )

        if not class_name:
            continue

        for target in node.targets:

            if isinstance(
                target,
                ast.Name,
            ):

                types[target.id] = class_name

    # ---------------------------------------------------------
    # Annotated assignments
    #
    #   resp: Response = ...
    # ---------------------------------------------------------

    for node in ast.walk(function_node):

        if not isinstance(
            node,
            ast.AnnAssign,
        ):
            continue

        if not isinstance(
            node.target,
            ast.Name,
        ):
            continue

        annotation = node.annotation

        if isinstance(
            annotation,
            ast.Name,
        ):

            types[node.target.id] = (
                annotation.id
            )

    return types

def resolve_call(
    call_node,
    current_class,
    local_types,
    symbol_table,
    class_method_table,
    inheritance_table,
):
    """
    Resolve a call conservatively.

    Returns:
        {
            "target": "...",
            "resolution": "internal"
        }

    or None when it cannot be safely resolved.
    """

    # ---------------------------------------------------------
    # Simple function call:
    #
    # connect()
    # ---------------------------------------------------------

    if isinstance(
        call_node.func,
        ast.Name,
    ):

        called_name = call_node.func.id

        candidates = symbol_table.get(
            called_name,
            [],
        )

        # Inside a class, prefer the current class method.
        if current_class:

            class_candidates = (
                class_method_table.get(
                    (
                        current_class,
                        called_name,
                    ),
                    [],
                )
            )

            if len(class_candidates) == 1:

                return {
                    "target": class_candidates[0],
                    "resolution": "internal",
                    "confidence": "high",
                }

        if len(candidates) == 1:

            return {
                "target": candidates[0]["id"],
                "resolution": "internal",
                "confidence": "medium",
            }

        if len(candidates) > 1:

            return {
                "target": called_name,
                "resolution": "ambiguous",
                "confidence": "low",
                "candidate_count": len(candidates),
            }

        return {
            "target": called_name,
            "resolution": "unresolved",
            "confidence": "unknown",
        }

    # ---------------------------------------------------------
    # Attribute call:
    #
    # self.close()
    # resp.close()
    # ---------------------------------------------------------

    if isinstance(
        call_node.func,
        ast.Attribute,
    ):

        method_name = call_node.func.attr
        root_name = get_attribute_root(
            call_node.func.value
        )

        # -----------------------------------------------------
        # self.method()
        # -----------------------------------------------------

        if (
            root_name == "self"
            and current_class
        ):

            candidates = find_class_method(
                current_class,
                method_name,
                class_method_table,
                inheritance_table,
            )

            if len(candidates) == 1:

                return {
                    "target": candidates[0],
                    "resolution": "internal",
                    "confidence": "high",
                }

        # -----------------------------------------------------
        # typed_variable.method()
        #
        # resp: Response
        # resp.close()
        # -----------------------------------------------------

        if root_name in local_types:

            class_name = local_types[
                root_name
            ]

            candidates = find_class_method(
                class_name,
                method_name,
                class_method_table,
                inheritance_table,
            )

            if len(candidates) == 1:

                return {
                    "target": candidates[0],
                    "resolution": "internal",
                    "confidence": "high",
                }

            if len(candidates) > 1:

                return {
                    "target": method_name,
                    "resolution": "ambiguous",
                    "confidence": "low",
                    "candidate_count": len(candidates),
                }

        # -----------------------------------------------------
        # Unknown object.
        #
        # We deliberately don't guess.
        # -----------------------------------------------------

        return {
            "target": method_name,
            "resolution": "unresolved",
            "confidence": "unknown",
        }

    return {
        "target": "unknown",
        "resolution": "unresolved",
        "confidence": "unknown",
    }


def extract_calls(
    file_path: Path,
    root: Path,
    symbol_table: dict,
    class_method_table: dict,
    inheritance_table: dict,
) -> list[dict]:

    source = file_path.read_text(
        encoding="utf-8",
        errors="ignore",
    )

    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []

    relative_path = file_path.relative_to(root)

    import_aliases = extract_import_aliases(tree)

    results = []

    def process_function(
        node,
        class_name=None,
    ):

        if class_name:

            source_id = (
                f"method:{relative_path}:"
                f"{class_name}.{node.name}"
            )

        else:

            source_id = (
                f"function:{relative_path}:"
                f"{node.name}"
            )

        local_types = extract_local_types(
            node,
            import_aliases,
        )

        resolved_calls = []

        for child in ast.walk(node):

            if not isinstance(
                child,
                ast.Call,
            ):
                continue

            resolved = resolve_call(
                child,
                class_name,
                local_types,
                symbol_table,
                class_method_table,
                inheritance_table,
            )

            if resolved:
                resolved_calls.append(resolved)

        results.append({
            "source": source_id,
            "calls": resolved_calls,
        })

    for node in tree.body:

        if isinstance(
            node,
            (ast.FunctionDef, ast.AsyncFunctionDef),
        ):

            process_function(node)

        elif isinstance(
            node,
            ast.ClassDef,
        ):

            for child in node.body:

                if isinstance(
                    child,
                    (ast.FunctionDef, ast.AsyncFunctionDef),
                ):

                    process_function(
                        child,
                        node.name,
                    )

    return results


def build_call_graph(
    repository_path: str,
) -> dict:

    root = Path(repository_path)

    python_files = get_python_files(root)

    symbol_table = {}

    for file_path in python_files:

        definitions = extract_definitions(
            file_path,
            root,
        )

        for name, entries in definitions.items():

            symbol_table.setdefault(
                name,
                [],
            ).extend(entries)

    class_method_table = build_class_method_table(
        python_files,
        root,
    )

    inheritance_table = build_class_inheritance_table(
        python_files,
        root,
    )

    all_calls = []

    for file_path in python_files:

        calls = extract_calls(
            file_path,
            root,
            symbol_table,
            class_method_table,
            inheritance_table,
        )

        all_calls.extend(calls)

    nodes = []
    edges = []

    # ---------------------------------------------------------
    # Add function/method nodes
    # ---------------------------------------------------------

    for name, entries in symbol_table.items():

        for entry in entries:

            nodes.append({
                "id": entry["id"],
                "type": entry["type"],
                "file": entry["id"].split(":", 2)[1],
            })

    # ---------------------------------------------------------
    # Add call edges
    # ---------------------------------------------------------

    for call_group in all_calls:

        source = call_group["source"]

        for call in call_group["calls"]:

            target = call["target"]

            edge = {
                "source": source,
                "target": target,
                "type": "calls",
                "resolution": call["resolution"],
            }

            if "confidence" in call:
                edge["confidence"] = call["confidence"]

            if "candidate_count" in call:
                edge["candidate_count"] = (
                    call["candidate_count"]
                )

            edges.append(edge)

    return {
        "repository": root.name,
        "nodes": nodes,
        "edges": edges,
    }

