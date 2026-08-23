from collections import defaultdict, deque


IMPACT_RELATIONSHIPS = {
    "calls",
    "imports",
}


def build_reverse_graph(edges: list[dict]) -> dict:
    reverse = defaultdict(list)

    for edge in edges:
        if edge["type"] not in IMPACT_RELATIONSHIPS:
            continue

        # For impact analysis, ignore unresolved calls.
        if edge["type"] == "calls":
            if edge.get("resolution") != "internal":
                continue

        reverse[edge["target"]].append(edge["source"])

    return reverse


def find_impact(
    graph: dict,
    target_id: str,
    max_depth: int = 5,
) -> dict:

    node_lookup = {
        node["id"]: node
        for node in graph["nodes"]
    }

    if target_id not in node_lookup:
        return {
            "target": target_id,
            "found": False,
            "message": "Target entity not found in repository graph.",
            "impacted_entities": [],
            "impact_count": 0,
        }

    reverse_graph = build_reverse_graph(
        graph["edges"]
    )

    queue = deque([
        (target_id, 0)
    ])

    visited = {target_id}
    impacted = []

    while queue:

        current, depth = queue.popleft()

        if depth >= max_depth:
            continue

        for parent in reverse_graph.get(
            current,
            [],
        ):

            if parent in visited:
                continue

            visited.add(parent)

            parent_node = node_lookup.get(parent)

            if parent_node:

                impacted.append({
                    "id": parent,
                    "type": parent_node["type"],
                    "name": parent_node.get("name"),
                    "file": parent_node.get("file"),
                    "depth": depth + 1,
                })

            queue.append(
                (parent, depth + 1)
            )

    direct = [
        item
        for item in impacted
        if item["depth"] == 1
    ]

    indirect = [
        item
        for item in impacted
        if item["depth"] > 1
    ]

    return {
        "target": {
            "id": target_id,
            "type": node_lookup[target_id]["type"],
            "name": node_lookup[target_id].get("name"),
            "file": node_lookup[target_id].get("file"),
        },
        "found": True,
        "max_depth": max_depth,
        "direct_impact": direct,
        "indirect_impact": indirect,
        "impact_count": len(impacted),
    }
