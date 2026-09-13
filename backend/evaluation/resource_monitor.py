"""Lightweight resource monitoring for RepoTwin evaluation."""

import os
import shutil
import subprocess
from typing import Any


def _gpu_memory_mb() -> float | None:
    """Return total GPU memory usage when nvidia-smi is available."""
    if not shutil.which("nvidia-smi"):
        return None

    try:
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=memory.used",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=2,
        )

        values = []
        for line in result.stdout.splitlines():
            line = line.strip()
            if line:
                values.append(float(line))

        return round(sum(values), 2) if values else None

    except Exception:
        return None


def snapshot() -> dict[str, Any]:
    """Capture current process/system resource information."""
    try:
        import psutil

        process = psutil.Process(os.getpid())

        return {
            "cpu_percent": psutil.cpu_percent(interval=0.1),
            "process_cpu_percent": process.cpu_percent(interval=0.1),
            "memory_mb": round(
                psutil.virtual_memory().used / (1024 * 1024),
                2,
            ),
            "process_memory_mb": round(
                process.memory_info().rss / (1024 * 1024),
                2,
            ),
            "gpu_memory_mb": _gpu_memory_mb(),
        }

    except Exception:
        return {
            "cpu_percent": None,
            "process_cpu_percent": None,
            "memory_mb": None,
            "process_memory_mb": None,
            "gpu_memory_mb": None,
        }
