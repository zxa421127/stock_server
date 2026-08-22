from __future__ import annotations

import ast
from pathlib import Path


def test_runtime_service_state_is_initialized_before_start_function():
    app_path = Path(__file__).resolve().parents[1] / "app.py"
    tree = ast.parse(app_path.read_text(encoding="utf-8"), filename=str(app_path))

    assignments: dict[str, tuple[object, int]] = {}
    function_lines: dict[str, int] = {}
    for node in tree.body:
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            value = node.value
            if not isinstance(value, ast.Constant):
                continue
            for target in targets:
                if isinstance(target, ast.Name):
                    assignments[target.id] = (value.value, node.lineno)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            function_lines[node.name] = node.lineno

    assert assignments["_web_services_started"][0] is False
    assert assignments["_runtime_started"][0] is False
    assert assignments["_runtime_started"][1] < function_lines["start_runtime_services"]
