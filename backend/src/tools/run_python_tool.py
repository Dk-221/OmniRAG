"""
run_python_tool – sandboxed Python execution.

Runs model-written Python in a subprocess with a 10-second timeout,
restricted environment, blocked dangerous modules, and a temp working dir.
Allowed: math, statistics, json, datetime, pandas, numpy.
Returns stdout + value of variable `result`. Generates a code artifact.
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path
from typing import Any, Dict, Optional

from src.tools._base import BaseTool, truncate

logger = logging.getLogger(__name__)

_TIMEOUT = 10  # seconds
_BLOCKED_MODULES = {
    "os", "sys", "subprocess", "socket", "shutil", "importlib",
    "ctypes", "multiprocessing", "threading", "pty", "atexit",
    "signal", "gc", "code", "codeop", "tokenize",
    "inspect", "dis", "traceback", "linecache", "ast", "urllib", "requests", "httpx"
}
_MAX_OUTPUT = 4000  # chars before truncation

_WRAPPER_TEMPLATE = textwrap.dedent("""\
# Pre-import allowed libraries first
import math, statistics, json, datetime
try:
    import numpy as np
except ImportError:
    pass
try:
    import pandas as pd
except ImportError:
    pass

# Now install sandbox security hook
_BLOCKED = {blocked_set!r}
_orig_import = __builtins__.__import__ if hasattr(__builtins__, '__import__') else __import__

def _safe_import(name, *args, **kwargs):
    base = name.split('.')[0]
    if base in _BLOCKED:
        raise ImportError(f"Module '{{name}}' is blocked in the sandbox.")
    return _orig_import(name, *args, **kwargs)

if isinstance(__builtins__, dict):
    __builtins__['__import__'] = _safe_import
else:
    __builtins__.__import__ = _safe_import

result = None
try:
{user_code}
except Exception as _e:
    print(f"[Error] {{_e}}")

# Print result variable if set
if result is not None:
    print(f"[result] {{result}}")
""")


class RunPythonTool(BaseTool):
    """Execute a Python code snippet in a restricted sandbox and return stdout."""

    name = "run_python"
    description = (
        "Execute Python code in a sandboxed subprocess with a 10s timeout. "
        "Allowed: math, statistics, json, datetime, numpy, pandas. Assign final answer to `result`."
    )
    parameters = {
        "type": "object",
        "properties": {
            "code": {
                "type": "string",
                "description": "Python code to execute. Assign final answer to `result`.",
            }
        },
        "required": ["code"],
    }
    category = "code"

    def __init__(self) -> None:
        self._last_artifact: Optional[Dict[str, Any]] = None

    def run(self, code: str, **_: Any) -> str:  # type: ignore[override]
        """Execute *code* safely and return stdout + result variable."""
        self._last_artifact = None

        # Indent user code for the wrapper template
        indented = textwrap.indent(code.strip(), "    ")
        script = _WRAPPER_TEMPLATE.format(
            blocked_set=_BLOCKED_MODULES,
            user_code=indented,
        )

        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            script_path = Path(tmp) / "script.py"
            script_path.write_text(script, encoding="utf-8")

            # Minimal environment so Python and C-runtime can start on Windows
            env = {
                "SYSTEMROOT": os.environ.get("SYSTEMROOT", "C:\\Windows"),
                "PATH": os.environ.get("PATH", ""),
                "PYTHONPATH": "",
            }

            try:
                proc = subprocess.run(
                    [sys.executable, str(script_path)],
                    capture_output=True,
                    text=True,
                    timeout=_TIMEOUT,
                    cwd=tmp,
                    env=env,
                )
                stdout = proc.stdout.strip()
                stderr = proc.stderr.strip()

                err_str = stderr if (stderr and not stdout) else (stderr if stderr else None)

                self._last_artifact = {
                    "kind": "code",
                    "data": {
                        "code": code,
                        "stdout": stdout,
                        "error": err_str,
                    },
                }

                if stderr and not stdout:
                    return truncate(f"[Error] {stderr}", _MAX_OUTPUT)
                combined = stdout
                if stderr:
                    combined += f"\n[stderr] {stderr}"
                return truncate(combined or "(no output)", _MAX_OUTPUT)

            except subprocess.TimeoutExpired:
                self._last_artifact = {
                    "kind": "code",
                    "data": {
                        "code": code,
                        "stdout": "",
                        "error": "Execution timed out (10 seconds)",
                    },
                }
                return "[Error] Code execution timed out (10 seconds)."
            except Exception as exc:
                self._last_artifact = {
                    "kind": "code",
                    "data": {
                        "code": code,
                        "stdout": "",
                        "error": str(exc),
                    },
                }
                return f"[Error] Could not execute code: {exc}"
