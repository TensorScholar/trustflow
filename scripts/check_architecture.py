from pathlib import Path

FORBIDDEN = {
    "src/trustflow/domain": ("fastapi", "sqlite3", "openpyxl", "docx", "pypdf", "typer"),
    "src/trustflow/application": ("fastapi", "openpyxl", "docx", "pypdf", "typer"),
}

violations = []
for directory, tokens in FORBIDDEN.items():
    for path in Path(directory).rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for token in tokens:
            if f"import {token}" in text or f"from {token}" in text:
                violations.append(f"{path}: imports {token}")
if violations:
    raise SystemExit("\n".join(violations))
print("architecture check passed")
