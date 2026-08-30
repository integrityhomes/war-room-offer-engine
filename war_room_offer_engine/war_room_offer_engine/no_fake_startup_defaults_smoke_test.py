from __future__ import annotations

import ast
from pathlib import Path


APP_PATH = Path(__file__).resolve().parent / "app.py"


def check(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)
    print(f"OK: {message}")


def field_defaults() -> dict[str, object]:
    tree = ast.parse(APP_PATH.read_text(encoding="utf-8"))
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if not any(isinstance(target, ast.Name) and target.id == "FIELD_DEFAULTS" for target in node.targets):
            continue
        value = ast.literal_eval(node.value)
        if not isinstance(value, dict):
            raise AssertionError("FIELD_DEFAULTS must remain a dictionary")
        return value
    raise AssertionError("FIELD_DEFAULTS was not found in app.py")


def main() -> None:
    defaults = field_defaults()
    expected_empty_evidence = {
        "asking_price": 0,
        "rent": 0,
        "beds": 0.0,
        "baths": 0.0,
        "sqft": 0,
    }
    for field, expected in expected_empty_evidence.items():
        actual = defaults.get(field)
        check(
            actual == expected,
            f"fresh-session {field} is empty evidence ({expected!r}), not a prototype value ({actual!r})",
        )


if __name__ == "__main__":
    main()
