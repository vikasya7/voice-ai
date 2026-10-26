
import ast
import operator
from langchain_core.tools import tool


@tool
def calculate(expression: str) -> str:
    """Calculate a mathematical expression using basic arithmetic."""
    operators = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.Pow: operator.pow,
        ast.USub: operator.neg,
        ast.UAdd: operator.pos,
    }

    def evaluate(node):
        if isinstance(node, ast.Constant) and type(node.value) in (int, float):
            return node.value

        if isinstance(node, ast.BinOp) and type(node.op) in operators:
            left = evaluate(node.left)
            right = evaluate(node.right)

            if isinstance(node.op, ast.Pow) and abs(right) > 10:
                raise ValueError("Exponent is too large")

            if isinstance(node.op, ast.Div) and right == 0:
                raise ValueError("Cannot divide by zero")

            return operators[type(node.op)](left, right)

        if isinstance(node, ast.UnaryOp) and type(node.op) in operators:
            return operators[type(node.op)](evaluate(node.operand))

        raise ValueError("Unsupported arithmetic expression")

    try:
        tree = ast.parse(expression, mode="eval")
        return str(evaluate(tree.body))
    except Exception as exc:
        return f"Calculation failed: {exc}"



import os
import httpx
from dotenv import load_dotenv
from langchain_core.tools import tool

load_dotenv()

@tool
def search_web(query: str) -> str:
    """Search the web for current information and return relevant results with source URLs."""
    api_key = os.getenv("PARALLEL_API_KEY")

    if not api_key:
        return "Parallel API key is missing. Configure PARALLEL_API_KEY in .env."

    try:
        response = httpx.post(
            "https://api.parallel.ai/v1beta/search",
            headers={
                "x-api-key": api_key,
                "Content-Type": "application/json",
            },
            json={
                "objective": query,
                "search_queries": [query],
            },
            timeout=30.0,
        )
        response.raise_for_status()
        data = response.json()

        return str(data)

    except httpx.HTTPStatusError as exc:
        return f"Web search failed with HTTP {exc.response.status_code}."
    except httpx.RequestError:
        return "Web search failed because the API could not be reached."
