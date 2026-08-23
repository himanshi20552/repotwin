from __future__ import annotations

import re


def _numbers(text: str) -> set[int]:
    return {
        int(value)
        for value in re.findall(r"\b\d+\b", text)
    }


def _all_evidence_text(evidence_package: dict) -> str:
    return str(evidence_package).lower()


def _history_commits(evidence_package: dict) -> set[str]:
    history = (
        evidence_package
        .get("analysis", {})
        .get("history", {})
    )

    commits = set()

    for commit in (
        history
        .get("file_history", {})
        .get("commits", [])
    ):
        value = commit.get("commit")

        if value:
            commits.add(value.lower())

    for commit in (
        history
        .get("symbol_history", {})
        .get("commits", [])
    ):
        value = commit.get("commit")

        if value:
            commits.add(value.lower())

    return commits


def _symbol_history_commits(
    evidence_package: dict,
) -> set[str]:

    history = (
        evidence_package
        .get("analysis", {})
        .get("history", {})
        .get("symbol_history", {})
    )

    return {
        commit.get("commit", "").lower()
        for commit in history.get("commits", [])
        if commit.get("commit")
    }


def _normalize_test_name(value: str) -> str:
    value = value.lower().strip()

    # Remove the entity-type prefix.
    if value.startswith("method:"):
        value = value[len("method:"):]

    if value.startswith("function:"):
        value = value[len("function:"):]

    # Normalize separators and whitespace.
    value = value.replace("\\", "/")
    value = re.sub(r"\\s+", "", value)

    return value


def _affected_test_names(
    evidence_package: dict,
) -> set[str]:

    tests = (
        evidence_package
        .get("analysis", {})
        .get("test_impact", {})
        .get("tests", [])
    )

    names = set()

    for test in tests:
        for value in (
            test.get("id"),
            test.get("name"),
        ):
            if value:
                normalized = _normalize_test_name(value)
                names.add(normalized)

    return names

def _affected_files(
    evidence_package: dict,
) -> set[str]:

    files = set()

    analysis = evidence_package.get(
        "analysis",
        {},
    )

    for section in (
        "production_impact",
        "test_impact",
    ):

        items = (
            analysis
            .get(section, {})
            .get(
                "direct",
                [],
            )
        )

        if section == "test_impact":
            items = (
                analysis
                .get(section, {})
                .get(
                    "tests",
                    [],
                )
            )

        for item in items:

            file_path = item.get("file")

            if file_path:
                files.add(
                    file_path.lower()
                )

    for item in (
        analysis
        .get("production_impact", {})
        .get("indirect", [])
    ):

        file_path = item.get("file")

        if file_path:
            files.add(
                file_path.lower()
            )

    return files


def validate_answer(
    answer: str,
    evidence_package: dict,
) -> dict:
    """
    Validate an LLM answer against structured repository evidence.

    The deterministic analysis remains the source of truth.
    """

    answer_lower = answer.lower()

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

    warnings = []
    unsupported_claims = []

    # ---------------------------------------------------------
    # 1. Commit validation
    # ---------------------------------------------------------

    commits = _history_commits(
        evidence_package
    )

    symbol_commits = _symbol_history_commits(
        evidence_package
    )

    mentioned_commits = re.findall(
        r"\b[0-9a-f]{7,40}\b",
        answer_lower,
    )

    for commit in mentioned_commits:

        if commit not in commits:
            unsupported_claims.append(
                f"Commit {commit} is not present in repository history evidence."
            )

    # If the answer explicitly associates a commit with
    # Response.close / the target symbol, require it to be
    # present in symbol history.
    history_phrases = [
        "symbol history",
        "method history",
        "response.close",
        "close method",
        "was added in commit",
        "was introduced in commit",
        "was modified in commit",
    ]

    mentions_symbol_history = any(
        phrase in answer_lower
        for phrase in history_phrases
    )

    if (
        mentions_symbol_history
        and mentioned_commits
        and symbol_commits
    ):

        for commit in mentioned_commits:

            if commit in commits and commit not in symbol_commits:

                unsupported_claims.append(
                    f"Commit {commit} is repository history evidence "
                    f"but is not supported by the supplied symbol history."
                )

    # ---------------------------------------------------------
    # 2. Deterministic metric validation
    # ---------------------------------------------------------

    expected_metrics = {
        "direct callers": production.get(
            "direct",
            [],
        ).__len__(),

        "indirect callers": production.get(
            "indirect",
            [],
        ).__len__(),

        "affected tests": tests.get(
            "count",
            0,
        ),

        "test count": tests.get(
            "count",
            0,
        ),

        "risk score": risk.get(
            "score",
            0,
        ),

        "risk": risk.get(
            "score",
            0,
        ),

        "high confidence paths": signals.get(
            "high_confidence_paths",
            0,
        ),

        "medium confidence paths": signals.get(
            "medium_confidence_paths",
            0,
        ),
    }

    for phrase, expected in expected_metrics.items():

        for match in re.finditer(
            re.escape(phrase),
            answer_lower,
        ):
            before = answer_lower[
                max(0, match.start() - 40):
                match.start()
            ]

            after = answer_lower[
                match.end():
                min(len(answer_lower), match.end() + 40)
            ]

            # Prefer a number immediately before the metric phrase.
            before_numbers = re.findall(
                r"\\b\\d+\\b\\s*$",
                before,
            )

            # Otherwise accept a number immediately after it.
            after_numbers = re.findall(
                r"^\\s*[:=]?\\s*(\\d+)\\b",
                after,
            )

            mentioned = None

            if before_numbers:
                mentioned = int(before_numbers[-1])
            elif after_numbers:
                mentioned = int(after_numbers[0])

            if (
                mentioned is not None
                and mentioned != expected
            ):
                unsupported_claims.append(
                    f"The claim '{phrase}' does not match "
                    f"the deterministic value {expected}."
                )
                break

    # ---------------------------------------------------------
    # 3. Test-name validation
    # ---------------------------------------------------------

    affected_tests = _affected_test_names(
        evidence_package
    )

    test_name_patterns = re.findall(
        r"`([^`]+)`",
        answer_lower,
    )

    for name in test_name_patterns:

        normalized_name = _normalize_test_name(name)

        if (
            "test" in normalized_name
            and normalized_name not in affected_tests
        ):
            warnings.append(
                f"Test '{name}' was not found in the affected-test evidence."
            )

    # ---------------------------------------------------------
    # 4. Unsupported certainty language
    # ---------------------------------------------------------

    risky_phrases = [
        "widespread use",
        "critical for",
        "security vulnerability",
        "data loss",
        "will definitely",
        "guarantees",
        "introduced in version",
        "removed in version",
        "originally introduced",
        "was added in",
    ]

    for phrase in risky_phrases:

        if phrase in answer_lower:

            warnings.append(
                f"Potentially unsupported assertion: '{phrase}'"
            )

    # ---------------------------------------------------------
    # 5. Determine final status
    # ---------------------------------------------------------

    if unsupported_claims:

        status = "REVIEW_REQUIRED"

    elif warnings:

        status = "CAUTION"

    else:

        status = "SUPPORTED"

    return {
        "status": status,
        "validated": status == "SUPPORTED",
        "unsupported_claims": unsupported_claims,
        "warnings": warnings,
        "claim_count": (
            len(unsupported_claims)
            + len(warnings)
        ),
    }
