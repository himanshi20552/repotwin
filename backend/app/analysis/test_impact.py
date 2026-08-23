from collections import deque


def find_test_impact(
    graph: dict,
    target_id: str,
    max_depth: int = 6,
) -> dict:

    edges = graph.get("edges", [])
    nodes = {
        node["id"]: node
        for node in graph.get("nodes", [])
    }

    # Build reverse call graph:
    #
    # target
    #   ↑
    # caller
    #   ↑
    # caller
    reverse = {}

    for edge in edges:

        if edge.get("type") != "calls":
            continue

        if edge.get("resolution") != "internal":
            continue

        source = edge["source"]
        target = edge["target"]

        # Ignore self-recursion.
        if source == target:
            continue

        reverse.setdefault(
            target,
            [],
        ).append(source)

    if target_id not in nodes:

        return {
            "target": target_id,
            "found": False,
            "tests": [],
            "test_count": 0,
        }

    queue = deque([
        (target_id, 0)
    ])

    visited = {
        target_id
    }

    affected_tests = {}

    while queue:

        current, depth = queue.popleft()

        if depth >= max_depth:
            continue

        for caller in reverse.get(
            current,
            [],
        ):

            if caller in visited:
                continue

            visited.add(caller)

            next_depth = depth + 1

            node = nodes.get(
                caller,
                {},
            )

            file_path = node.get(
                "file",
                "",
            )

            if file_path.startswith(
                "tests/"
            ):

                affected_tests[caller] = {
                    "id": caller,
                    "type": node.get("type"),
                    "name": node.get("name"),
                    "file": file_path,
                    "depth": next_depth,
                }

            queue.append(
                (
                    caller,
                    next_depth,
                )
            )

    tests = list(
        affected_tests.values()
    )

    tests.sort(
        key=lambda item: (
            item["depth"],
            item["file"],
            item["name"] or "",
        )
    )

    return {
        "target": target_id,
        "found": True,
        "max_depth": max_depth,
        "tests": tests,
        "test_count": len(tests),
    }
