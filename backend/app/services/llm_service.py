import requests
from app.validation.evidence_validator import validate_answer


OLLAMA_URL = "http://localhost:11434/api/generate"
DEFAULT_MODEL = "qwen2.5-coder:1.5b"


def generate_with_ollama(
    prompt: str,
    model: str = DEFAULT_MODEL,
    timeout: int = 300,
) -> str:

    response = requests.post(
        OLLAMA_URL,
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

    return data.get(
        "response",
        "",
    )


def build_engineering_prompt(
    retrieval_context: dict,
) -> str:

    target = retrieval_context.get(
        "target",
        {},
    )

    risk = retrieval_context.get(
        "risk",
        {},
    )

    evidence = retrieval_context.get(
        "retrieved_evidence",
        [],
    )

    history = retrieval_context.get(
        "history",
        {},
    )

    file_history = history.get(
        "file_history",
        {},
    )

    symbol_history = history.get(
        "symbol_history",
        {},
    )

    commits = file_history.get(
        "commits",
        [],
    )

    symbol_commits = symbol_history.get(
        "commits",
        [],
    )

    evidence_lines = []

    for index, item in enumerate(
        evidence,
        start=1,
    ):
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

    evidence_text = "\n".join(
        evidence_lines
    ) or "No graph evidence supplied."

    commit_lines = []

    for commit in commits[:5]:
        commit_lines.append(
            f"- {commit.get('date')} "
            f"{commit.get('commit')} "
            f"{commit.get('message')}"
        )

    commit_text = "\n".join(
        commit_lines
    ) or "No file-history evidence supplied."

    symbol_commit_lines = []

    for commit in symbol_commits[:10]:
        symbol_commit_lines.append(
            f"- {commit.get('date')} "
            f"{commit.get('commit')} "
            f"{commit.get('message')}"
        )

    symbol_commit_text = (
        "\n".join(symbol_commit_lines)
        or "No symbol-history evidence supplied."
    )

    production_count = retrieval_context.get(
        "production_impact_count",
        0,
    )

    test_count = retrieval_context.get(
        "test_impact_count",
        0,
    )

    direct_callers = len(
        retrieval_context.get(
            "risk",
            {},
        ).get(
            "signals",
            {},
        ).get(
            "direct_callers",
            [],
        )
        if isinstance(
            retrieval_context.get(
                "risk",
                {},
            ).get(
                "signals",
                {},
            ).get(
                "direct_callers",
                0,
            ),
            list,
        )
        else []
    )

    signals = risk.get(
        "signals",
        {},
    )

    direct_callers = signals.get(
        "direct_callers",
        0,
    )

    indirect_callers = signals.get(
        "indirect_callers",
        0,
    )

    risk_score = risk.get(
        "score",
        0,
    )

    risk_level = risk.get(
        "level",
        "UNKNOWN",
    )

    return f"""
You are RepoTwin.

You are NOT a general-purpose software expert for this task.
You must answer ONLY from the deterministic repository evidence
provided below.

TARGET:
{target}

DETERMINISTIC FACTS:

Production impact count = {production_count}
Direct callers = {direct_callers}
Indirect callers = {indirect_callers}
Affected tests = {test_count}
Risk score = {risk_score}
Risk level = {risk_level}

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
2. NEVER use pretrained knowledge about Requests or any other repository.
3. NEVER infer what the target method does internally.
4. NEVER invent implementation details, consequences, dependencies,
   bugs, vulnerabilities, performance effects, resource effects, or
   business effects.
5. NEVER describe the impact as "significant", "critical", "widespread",
   "extensive", "crucial", "likely", or similar qualitative language.
6. The IMPACT section must contain ONLY the exact production impact,
   direct caller, and indirect caller numbers.
7. The RISK section must contain ONLY the exact risk score and risk level.
   Do NOT explain what the risk means.
8. The AFFECTED TESTS section must contain ONLY the exact test count,
   unless an exact test entity is present in CODE-GRAPH EVIDENCE.
9. NEVER mention a test file by itself as evidence of affected tests.
10. NEVER claim a commit changed, added, removed, or modified the target
    method unless that commit appears in SYMBOL HISTORY.
11. FILE HISTORY is NOT proof that a commit changed the target symbol.
12. If SYMBOL HISTORY does not establish a requested historical fact,
    say exactly:
    "The supplied repository evidence does not establish this."
13. Do not mention data loss, security vulnerabilities, resource leaks,
    performance problems, network problems, or other consequences.
14. Do not change, estimate, reinterpret, or calculate deterministic
    numerical values.
15. For the recommendation, say exactly:
    "Review the change carefully and run the affected tests."
16. Do not add claims beyond the requested five sections.
17. Keep the answer concise.

ANSWER FORMAT:

Return ONLY these five sections.
Do not include instructions, meta-commentary, or the word "State:".

1. Impact
Write one natural sentence containing the exact production impact,
direct caller, and indirect caller values from DETERMINISTIC FACTS.

2. Risk
Write one natural sentence containing the exact risk score and risk
level from DETERMINISTIC FACTS.

3. Affected tests
Write one natural sentence containing the exact affected-test count.
Only list individual tests if their exact entities appear in the
supplied CODE-GRAPH EVIDENCE.

4. Relevant history
Discuss only SYMBOL HISTORY.
If SYMBOL HISTORY does not establish a historical fact relevant to the
question, write exactly:
"The supplied repository evidence does not establish this."

5. Recommendation
Write exactly:
"Review the change carefully and run the affected tests."

Do not add any claims beyond the supplied evidence.
Do not repeat the instructions.
""".strip()

def analyze_with_ollama(
    retrieval_context: dict,
    model: str = DEFAULT_MODEL,
) -> dict:
    """
    Generate an optional AI explanation while keeping the core
    engineering answer deterministic and evidence-grounded.
    """

    evidence_package = retrieval_context.get(
        "evidence_package",
        retrieval_context,
    )

    analysis = evidence_package.get(
        "analysis",
        {},
    )

    production = analysis.get(
        "production_impact",
        {},
    )

    tests = analysis.get(
        "test_impact",
        {},
    )

    risk = analysis.get(
        "risk",
        {},
    )

    signals = risk.get(
        "signals",
        {},
    )

    direct_callers = signals.get(
        "direct_callers",
        0,
    )

    indirect_callers = signals.get(
        "indirect_callers",
        0,
    )

    production_count = production.get(
        "count",
        0,
    )

    test_count = tests.get(
        "count",
        0,
    )

    risk_score = risk.get(
        "score",
        0,
    )

    risk_level = risk.get(
        "level",
        "UNKNOWN",
    )

    history = analysis.get(
        "history",
        {},
    )

    symbol_history = history.get(
        "symbol_history",
        {},
    )

    symbol_commits = symbol_history.get(
        "commits",
        [],
    )

    if symbol_commits:
        history_text = (
            "The supplied symbol history contains "
            f"{len(symbol_commits)} commit(s)."
        )
    else:
        history_text = (
            "The supplied repository evidence does not establish this."
        )

    deterministic_answer = (
        "1. Impact\n"
        f"The deterministic analysis found {production_count} "
        "production impact entities, including "
        f"{direct_callers} direct callers and "
        f"{indirect_callers} indirect callers.\n\n"

        "2. Risk\n"
        f"The deterministic risk score is {risk_score} "
        f"({risk_level}).\n\n"

        "3. Affected tests\n"
        f"The deterministic analysis found {test_count} "
        "affected tests.\n\n"

        "4. Relevant history\n"
        f"{history_text}\n\n"

        "5. Recommendation\n"
        "Review the change carefully and run the affected tests."
    )

    validation = validate_answer(
        deterministic_answer,
        evidence_package,
    )

    return {
        "model": model,
        "answer": deterministic_answer,
        "ai_explanation": "",
        "validation": validation,
    }
