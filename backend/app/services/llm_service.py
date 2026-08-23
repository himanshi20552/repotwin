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

    # Retrieved code chunks (RAG context)
    chunk_lines = []
    for index, chunk in enumerate(code_chunks, start=1):
        meta = chunk.get("metadata", chunk)
        chunk_lines.append(
            f"--- CODE CHUNK {index} (Similarity: {chunk.get('similarity_score', 0):.2f}) ---\n"
            f"Entity: {meta.get('entity_id') or meta.get('name')}\n"
            f"File: {meta.get('file')}:{meta.get('start_line', 1)}-{meta.get('end_line', 1)}\n"
            f"Type: {meta.get('type')}\n"
            f"Source Code:\n{chunk.get('source_code', '')[:800]}\n"
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

You are analyzing a proposed change to a codebase.
You must answer using ONLY the supplied deterministic facts, Git history, graph evidence, and retrieved code chunks below.

TARGET ENTITY:
{target}

DETERMINISTIC FACTS (AUTHORITATIVE):
- Production impact count = {production_count}
- Direct callers = {direct_callers}
- Indirect callers = {indirect_callers}
- Affected tests = {test_count}
- Risk score = {risk_score}
- Risk level = {risk_level}

RETRIEVED CODE CHUNKS (RAG KNOWLEDGE BASE):
{code_chunks_text}

FILE HISTORY:
{commit_text}

SYMBOL HISTORY:
{symbol_commit_text}

CODE-GRAPH EVIDENCE:
{evidence_text}

USER QUESTION:
{retrieval_context.get("query", "")}

STRICT RULES:
1. Use ONLY the supplied deterministic facts and evidence.
2. The IMPACT section must contain ONLY the exact production impact, direct caller, and indirect caller numbers.
3. The RISK section must contain ONLY the exact risk score and risk level.
4. The AFFECTED TESTS section must contain ONLY the exact test count.
5. If SYMBOL HISTORY does not establish a requested historical fact, say exactly:
   "The supplied repository evidence does not establish this."
6. Recommendation must state: "Review the change carefully and run the affected tests."

ANSWER FORMAT:
Return these five sections:
1. Impact
2. Risk
3. Affected tests
4. Relevant history
5. Recommendation
""".strip()


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
            timeout=30,
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
