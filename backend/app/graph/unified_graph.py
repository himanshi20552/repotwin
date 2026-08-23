from app.graph.typed_graph import build_typed_graph
from app.graph.repository_graph import build_repository_graph
from app.graph.call_graph import build_call_graph


def build_unified_graph(repository_path: str) -> dict:

    typed = build_typed_graph(repository_path)
    dependencies = build_repository_graph(repository_path)
    calls = build_call_graph(repository_path)

    nodes = typed["nodes"].copy()
    edges = typed["edges"].copy()

    existing_node_ids = {
        node["id"]
        for node in nodes
    }

    for node in dependencies["nodes"]:

        node_id = f"file:{node['id']}"

        if node_id not in existing_node_ids:

            nodes.append({
                "id": node_id,
                "type": "file",
                "name": node["id"],
                "language": node.get("language"),
            })

            existing_node_ids.add(node_id)

    for edge in dependencies["edges"]:

        edges.append({
            "source": f"file:{edge['source']}",
            "target": edge["target"],
            "type": edge["type"],
            "dependency": edge.get("dependency"),
        })

    for edge in calls["edges"]:

        call_edge = {
            "source": edge["source"],
            "target": edge["target"],
            "type": "calls",
            "resolution": edge.get("resolution"),
        }

        if edge.get("confidence") is not None:
            call_edge["confidence"] = edge["confidence"]

        if edge.get("candidate_count") is not None:
            call_edge["candidate_count"] = (
                edge["candidate_count"]
            )

        edges.append(call_edge)

    return {
        "repository": typed["repository"],
        "repository_path": str(repository_path),
        "nodes": nodes,
        "edges": edges,
    }
