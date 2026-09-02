import os
import requests
from typing import Any
from app.validation.evidence_validator import validate_answer


def get_ollama_base_url() -> str:
    url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
    if not url.startswith("http://") and not url.startswith("https://"):
        url = f"http://{url}"
    return url


def get_default_model() -> str:
    return os.getenv("OLLAMA_MODEL", "codellama:7b")


def check_ollama_health(base_url: str | None = None) -> dict[str, Any]:
    url = base_url or get_ollama_base_url()
    try:
        resp = requests.get(f"{url}/api/tags", timeout=3)
        if resp.status_code == 200:
            models = [m.get("name") for m in resp.json().get("models", [])]
            return {"available": True, "models": models, "url": url}
        return {"available": False, "models": [], "url": url, "status_code": resp.status_code}
    except Exception as exc:
        return {"available": False, "models": [], "url": url, "error": str(exc)}


def generate_with_ollama(
    prompt: str,
    model: str | None = None,
    base_url: str | None = None,
    timeout: int = 120,
) -> str:
    model = model or get_default_model()
    url = base_url or get_ollama_base_url()
    endpoint = f"{url}/api/generate"

    response = requests.post(
        endpoint,
        json={
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.1,
                "num_ctx": 4096,
                "num_predict": 500,
            },
        },
        timeout=timeout,
    )
    response.raise_for_status()
    data = response.json()
    return data.get("response", "")


def build_rag_prompt(retrieval_context: dict[str, Any]) -> str:
    target = retrieval_context.get("target", {})
    risk = retrieval_context.get("risk", {})
    evidence = retrieval_context.get("retrieved_evidence", [])
    code_chunks = retrieval_context.get("retrieved_code_chunks", [])
    history = retrieval_context.get("history", {})

    file_history = history.get("file_history", {})
    symbol_history = history.get("symbol_history", {})
    commits = file_history.get("commits", [])
    symbol_commits = symbol_history.get("commits", [])

    # Graph evidence
    evidence_lines = []
    for index, item in enumerate(evidence, start=1):
        evidence_lines.append(
            f"EVIDENCE {index}\n"
            f"category: {item.get('category')}\n"
            f"relationship: {item.get('relationship')}\n"
            f"source: {item.get('source')}\n"
            f"source_name: {item.get('source_name')}\n"
            f"file: {item.get('file')}\n"
            f"depth: {item.get('depth')}\n"
            f"confidence: {item.get('confidence')}\n"
        )
    evidence_text = "\n".join(evidence_lines) or "No graph evidence supplied."

    # Retrieved code chunks
    chunk_lines = []
    for index, chunk in enumerate(code_chunks, start=1):
        meta = chunk.get("metadata", chunk)
        chunk_lines.append(
            f"--- CODE CHUNK {index} (Similarity: {chunk.get('similarity_score', 0):.2f}) ---\n"
            f"Entity: {meta.get('entity_id') or meta.get('name')}\n"
            f"File: {meta.get('file')}:{meta.get('start_line', 1)}-{meta.get('end_line', 1)}\n"
            f"Type: {meta.get('type')}\n"
            f"Source Code:\n{chunk.get('source_code', '')[:1200]}\n"
        )
    code_chunks_text = "\n".join(chunk_lines) or "No code chunks retrieved."

    # Commits
    commit_lines = [
        f"- {c.get('date')} {c.get('commit')} {c.get('message')}"
        for c in commits[:5]
    ]
    commit_text = "\n".join(commit_lines) or "No file-history evidence supplied."

    symbol_commit_lines = [
        f"- {c.get('date')} {c.get('commit')} {c.get('message')}"
        for c in symbol_commits[:10]
    ]
    symbol_commit_text = "\n".join(symbol_commit_lines) or "No symbol-history evidence supplied."

    production_count = retrieval_context.get("production_impact_count", 0)
    test_count = retrieval_context.get("test_impact_count", 0)
    signals = risk.get("signals", {})
    direct_callers = signals.get("direct_callers", 0)
    indirect_callers = signals.get("indirect_callers", 0)
    risk_score = risk.get("score", 0)
    risk_level = risk.get("level", "UNKNOWN")

    return f"""
You are RepoTwin, an AI code intelligence assistant.

You are analyzing a proposed change to a software repository.

Your task is to provide a DETAILED, repository-grounded engineering analysis.

Use the supplied deterministic analysis, code graph evidence, retrieved source code,
and Git history as your evidence.

Do NOT invent files, functions, callers, tests, commits, dependencies, or behavior.
If the supplied evidence does not establish something, explicitly say that it is not
established by the repository evidence.

TARGET ENTITY:
{target}

DETERMINISTIC FACTS (AUTHORITATIVE):
- Production impact count = {production_count}
- Direct callers = {direct_callers}
- Indirect callers = {indirect_callers}
- Affected tests = {test_count}
- Risk score = {risk_score}
- Risk level = {risk_level}

RETRIEVED CODE CHUNKS:
{code_chunks_text}

FILE HISTORY:
{commit_text}

SYMBOL HISTORY:
{symbol_commit_text}

CODE-GRAPH EVIDENCE:
{evidence_text}

USER QUESTION:
{retrieval_context.get("query", "")}

RESPONSE FORMAT:

1. Impact

State the exact production impact count, direct caller count, and indirect caller
count from the deterministic analysis.

Then explain what the available repository evidence indicates about the impact.
Use specific files, functions, entities, relationships, and retrieved source code
when they are actually present in the supplied evidence.

Explain how the proposed change could propagate through the repository based only
on the supplied dependency information.

2. Risk

State the exact risk score and risk level.

Then explain WHY the repository analysis considers the change risky. Discuss the
available dependency relationships, production impact, affected files, and graph
evidence when supported by the supplied data.

Do not change or recalculate the deterministic risk score.

3. Affected Tests

State the exact affected test count.

Then explain what the supplied repository evidence indicates about the affected
tests. Mention specific test files or test entities only when they appear in the
evidence.

4. Relevant History

Summarize relevant file or symbol history from the supplied Git history.

Explain why a commit is relevant only when that relevance is supported by the
provided history.

If the history does not establish a useful historical fact, say:
"The supplied repository evidence does not establish this."

5. Recommendation

Give a concise repository-specific recommendation based on the evidence.

The recommendation must include:
"Review the change carefully and run the affected tests."

GROUNDING RULES:

- Deterministic numbers are authoritative and must be preserved exactly.
- Retrieved repository evidence takes priority over general model knowledge.
- Do not make generic claims when repository evidence is available.
- Do not invent repository details.
- Clearly distinguish repository evidence from general engineering reasoning.
- Provide useful explanation rather than merely repeating the deterministic summary.
- The answer should be detailed enough to explain the reasoning behind the impact
  and risk assessment.
"""


def build_non_rag_prompt(target: dict[str, Any], query: str) -> str:
    target_name = target.get("name") or target.get("id") or str(target)
    target_file = target.get("file", "")
    return f"""
You are a software engineering assistant.

A developer is asking the following question about the codebase:
Target: {target_name} (File: {target_file})
Question: {query}

Please answer the question based on your general software engineering knowledge without repository-specific graph evidence or retrieved code chunks.
""".strip()


def analyze_with_ollama(
    retrieval_context: dict[str, Any],
    model: str | None = None,
    use_rag: bool = True,
) -> dict[str, Any]:
    """
    Generate an AI explanation while keeping the core engineering answer deterministic
    and grounded in repository evidence.
    """
    model_to_use = model or get_default_model()
    base_url = get_ollama_base_url()

    evidence_package = retrieval_context.get("evidence_package", retrieval_context)
    analysis = evidence_package.get("analysis", {})
    production = analysis.get("production_impact", {})
    tests = analysis.get("test_impact", {})
    risk = analysis.get("risk", {})
    signals = risk.get("signals", {})

    direct_callers = signals.get("direct_callers", 0)
    indirect_callers = signals.get("indirect_callers", 0)
    production_count = production.get("count", 0)
    test_count = tests.get("count", 0)
    risk_score = risk.get("score", 0)
    risk_level = risk.get("level", "UNKNOWN")

    history = analysis.get("history", {})
    symbol_history = history.get("symbol_history", {})
    symbol_commits = symbol_history.get("commits", [])

    if symbol_commits:
        history_text = f"The supplied symbol history contains {len(symbol_commits)} commit(s)."
    else:
        history_text = "The supplied repository evidence does not establish this."

    deterministic_answer = (
        "1. Impact\n"
        f"The deterministic analysis found {production_count} production impact entities, "
        f"including {direct_callers} direct callers and {indirect_callers} indirect callers.\n\n"
        "2. Risk\n"
        f"The deterministic risk score is {risk_score} ({risk_level}).\n\n"
        "3. Affected tests\n"
        f"The deterministic analysis found {test_count} affected tests.\n\n"
        "4. Relevant history\n"
        f"{history_text}\n\n"
        "5. Recommendation\n"
        "Review the change carefully and run the affected tests."
    )

    prompt = (
        build_rag_prompt(retrieval_context)
        if use_rag
        else build_non_rag_prompt(
            retrieval_context.get("target", {}),
            retrieval_context.get("query", ""),
        )
    )

    ollama_response = ""
    ollama_available = False
    ollama_error = None

    try:
        ollama_response = generate_with_ollama(
            prompt=prompt,
            model=model_to_use,
            base_url=base_url,
            timeout=180,
        )
        ollama_available = True
    except Exception as exc:
        ollama_error = f"Ollama model '{model_to_use}' at {base_url} unavailable: {exc}"
        ollama_available = False

    # Choose answer for display
    if use_rag:
        # Grounded answer is authoritative
        answer_for_validation = deterministic_answer
        final_answer = deterministic_answer
        if ollama_response:
            final_answer = f"{deterministic_answer}\n\n[Code Llama Output]:\n{ollama_response}"
    else:
        # Non-RAG output demonstrates ungrounded generation
        if ollama_response:
            final_answer = ollama_response
            answer_for_validation = ollama_response
        else:
            final_answer = f"(Non-RAG mode) General response generated without repository evidence. {ollama_error or ''}"
            answer_for_validation = final_answer

    validation = validate_answer(
        answer_for_validation,
        evidence_package,
    )

    return {
        "model": model_to_use,
        "ollama_available": ollama_available,
        "mode": "rag" if use_rag else "non_rag",
        "answer": final_answer,
        "ai_explanation": ollama_response,
        "validation": validation,
        "prompt": prompt,
        "error": ollama_error,
    }
