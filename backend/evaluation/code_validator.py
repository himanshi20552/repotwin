"""Validation utilities for generated code."""

import ast
import re
from typing import Any


def extract_python_code(answer: str) -> str | None:
    """Extract the first Python fenced code block."""
    if not answer:
        return None

    match = re.search(
        r"```(?:python|py)\s*\n(.*?)```",
        answer,
        re.DOTALL | re.IGNORECASE,
    )

    if match:
        return match.group(1).strip()

    return None


def validate_generated_code(answer: str) -> dict[str, Any]:
    """Check whether generated Python code parses successfully."""
    code = extract_python_code(answer)

    if not code:
        return {
            "applicable": False,
            "passed": False,
            "reason": "No Python code block found",
        }

    try:
        ast.parse(code)

        return {
            "applicable": True,
            "passed": True,
            "reason": "Python syntax valid",
        }

    except SyntaxError as exc:
        return {
            "applicable": True,
            "passed": False,
            "reason": f"SyntaxError: {exc}",
        }

    except Exception as exc:
        return {
            "applicable": True,
            "passed": False,
            "reason": f"Validation error: {exc}",
        }
