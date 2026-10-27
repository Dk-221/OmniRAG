"""
calculator_tool – safe AST-based math evaluator.

NEVER uses Python's built-in eval(). Instead, it walks the AST and only
allows a whitelist of safe nodes (numbers, basic operators, math functions).
This prevents code injection attacks.
"""

from __future__ import annotations

import ast
import logging
import math
import operator
from typing import Any, Union

from src.tools._base import BaseTool

logger = logging.getLogger(__name__)

# Allowed binary operators
_BINOP = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.Mod: operator.mod,
    ast.FloorDiv: operator.floordiv,
}

# Allowed unary operators
_UNOP = {
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}

# Allowed math functions (safe subset)
_FUNCTIONS: dict[str, Any] = {
    "abs": abs,
    "round": round,
    "sqrt": math.sqrt,
    "log": math.log,
    "log10": math.log10,
    "log2": math.log2,
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "asin": math.asin,
    "acos": math.acos,
    "atan": math.atan,
    "atan2": math.atan2,
    "exp": math.exp,
    "floor": math.floor,
    "ceil": math.ceil,
    "factorial": math.factorial,
    "gcd": math.gcd,
    "pow": pow,
    "min": min,
    "max": max,
    "sum": sum,
}

# Allowed constants
_CONSTANTS: dict[str, float] = {
    "pi": math.pi,
    "e": math.e,
    "tau": math.tau,
    "inf": math.inf,
}


class _SafeEvaluator(ast.NodeVisitor):
    """Walk an AST and compute the result using only whitelisted operations."""

    def visit(self, node: ast.AST) -> Any:
        method = f"visit_{type(node).__name__}"
        visitor = getattr(self, method, self._forbidden)
        return visitor(node)

    def _forbidden(self, node: ast.AST) -> None:
        raise ValueError(f"Unsafe expression node: {type(node).__name__}")

    # ── literals ──────────────────────────────────────────────────────────
    def visit_Expression(self, node: ast.Expression) -> Any:
        return self.visit(node.body)

    def visit_Constant(self, node: ast.Constant) -> Any:
        if isinstance(node.value, (int, float, complex)):
            return node.value
        raise ValueError(f"Non-numeric constant: {node.value!r}")

    # ── names (constants like pi, e) ──────────────────────────────────────
    def visit_Name(self, node: ast.Name) -> Any:
        if node.id in _CONSTANTS:
            return _CONSTANTS[node.id]
        raise ValueError(f"Unknown name: {node.id!r}")

    # ── operators ─────────────────────────────────────────────────────────
    def visit_BinOp(self, node: ast.BinOp) -> Any:
        op_fn = _BINOP.get(type(node.op))
        if op_fn is None:
            raise ValueError(f"Unsupported binary operator: {type(node.op).__name__}")
        left = self.visit(node.left)
        right = self.visit(node.right)
        return op_fn(left, right)

    def visit_UnaryOp(self, node: ast.UnaryOp) -> Any:
        op_fn = _UNOP.get(type(node.op))
        if op_fn is None:
            raise ValueError(f"Unsupported unary operator: {type(node.op).__name__}")
        return op_fn(self.visit(node.operand))

    # ── function calls ────────────────────────────────────────────────────
    def visit_Call(self, node: ast.Call) -> Any:
        if not isinstance(node.func, ast.Name):
            raise ValueError("Only simple function calls are allowed.")
        fn = _FUNCTIONS.get(node.func.id)
        if fn is None:
            raise ValueError(f"Unknown function: {node.func.id!r}")
        if node.keywords:
            raise ValueError("Keyword arguments are not allowed.")
        args = [self.visit(a) for a in node.args]
        return fn(*args)

    # ── tuple / list for multi-arg min/max/sum ────────────────────────────
    def visit_Tuple(self, node: ast.Tuple) -> tuple:
        return tuple(self.visit(el) for el in node.elts)

    def visit_List(self, node: ast.List) -> list:
        return [self.visit(el) for el in node.elts]


def safe_eval(expression: str) -> Union[int, float, complex]:
    """
    Parse *expression* as a Python math expression and evaluate it safely.

    Raises ``ValueError`` for any unsafe or invalid expression.
    """
    try:
        tree = ast.parse(expression.strip(), mode="eval")
    except SyntaxError as exc:
        raise ValueError(f"Syntax error in expression: {exc}") from exc
    return _SafeEvaluator().visit(tree)


class CalculatorTool(BaseTool):
    """Evaluate mathematical expressions safely without using eval()."""

    name = "calculate"
    category = "utility"
    description = (
        "Evaluate a mathematical expression safely and return the numeric result. "
        "Supports arithmetic, powers, modulo, trigonometry, log, sqrt, and common math functions."
    )
    parameters = {
        "type": "object",
        "properties": {
            "expression": {
                "type": "string",
                "description": (
                    "A valid mathematical expression string. "
                    "Use Python syntax, e.g. '2 ** 10' for powers, "
                    "'sqrt(16)' for square root."
                ),
            }
        },
        "required": ["expression"],
    }

    def run(self, expression: str, **_: Any) -> str:  # type: ignore[override]
        """Evaluate *expression* and return the result as a string."""
        expr = expression.strip()
        logger.info("Calculator: %s", expr)
        try:
            result = safe_eval(expr)
            # Format cleanly
            if isinstance(result, float) and result.is_integer():
                result = int(result)
            return f"{expr} = {result}"
        except ValueError as exc:
            return f"Invalid expression: {exc}"
        except ZeroDivisionError:
            return "Math error: Division by zero."
        except OverflowError:
            return "Math error: Result too large to compute."
