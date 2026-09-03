"""Freeze and verify the TrustFlow v0.1 release-candidate compatibility surface."""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import tempfile
from enum import Enum
from pathlib import Path
from typing import Any

import click
from typer.main import get_command

import trustflow
from trustflow.adapters.sqlite import SQLiteStore
from trustflow.cli import app as cli_app
from trustflow.domain.models import DraftAnswer, Questionnaire, ReviewDecision, SourceDocument
from trustflow.web.app import (
    GovernanceMetricsResponse,
    MetricsResponse,
    QuestionnaireResponse,
    ReviewRequest,
    create_app,
)

CONTRACT_LOCK_PATH = Path("compatibility/v0.1-contract.json")


def _json_value(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    return repr(value)


def _click_param(param: click.Parameter) -> dict[str, object]:
    result: dict[str, object] = {
        "name": param.name,
        "kind": "option" if isinstance(param, click.Option) else "argument",
        "required": bool(param.required),
        "nargs": param.nargs,
        "multiple": bool(getattr(param, "multiple", False)),
        "type": getattr(param.type, "name", type(param.type).__name__),
    }
    if isinstance(param, click.Option):
        result["opts"] = sorted([*param.opts, *param.secondary_opts])
    if isinstance(param.type, click.Choice):
        result["choices"] = list(param.type.choices)
    default = getattr(param, "default", None)
    if default is not None:
        result["default"] = _json_value(default)
    return result


def _cli_contract() -> dict[str, object]:
    command = get_command(cli_app)
    commands = getattr(command, "commands", None)
    if not isinstance(commands, dict):
        raise RuntimeError("TrustFlow CLI root does not expose a command mapping")
    return {
        "root_params": [_click_param(param) for param in command.params],
        "commands": {
            name: {
                "params": [_click_param(param) for param in child.params],
            }
            for name, child in sorted(commands.items())
        },
    }


def _openapi_contract() -> dict[str, object]:
    with tempfile.TemporaryDirectory(prefix="trustflow-contract-") as directory:
        root = Path(directory)
        schema = create_app(root / "contract.db", root / "uploads").openapi()
    info = schema.get("info")
    if isinstance(info, dict) and "version" in info:
        info["version"] = "<package-version>"
    return schema


def _model_schemas() -> dict[str, object]:
    models = (
        SourceDocument,
        Questionnaire,
        DraftAnswer,
        ReviewDecision,
        ReviewRequest,
        QuestionnaireResponse,
        MetricsResponse,
        GovernanceMetricsResponse,
    )
    return {model.__name__: model.model_json_schema() for model in models}


def _sqlite_contract() -> dict[str, object]:
    with tempfile.TemporaryDirectory(prefix="trustflow-contract-sqlite-") as directory:
        database = Path(directory) / "contract.db"
        SQLiteStore(database)
        connection = sqlite3.connect(database)
        try:
            tables: dict[str, object] = {}
            table_names = [
                row[0]
                for row in connection.execute(
                    """
                    SELECT name FROM sqlite_master
                    WHERE type='table' AND name NOT LIKE 'sqlite_%'
                    ORDER BY name
                    """
                ).fetchall()
            ]
            for table in table_names:
                columns = [
                    {
                        "name": row[1],
                        "type": row[2],
                        "notnull": bool(row[3]),
                        "default": row[4],
                        "primary_key_position": row[5],
                    }
                    for row in connection.execute(f'PRAGMA table_info("{table}")').fetchall()
                ]
                indexes = []
                for row in connection.execute(f'PRAGMA index_list("{table}")').fetchall():
                    index_name = row[1]
                    if index_name.startswith("sqlite_autoindex_"):
                        continue
                    indexes.append(
                        {
                            "name": index_name,
                            "unique": bool(row[2]),
                            "columns": [
                                item[2]
                                for item in connection.execute(
                                    f'PRAGMA index_info("{index_name}")'
                                ).fetchall()
                            ],
                        }
                    )
                tables[table] = {
                    "columns": columns,
                    "indexes": sorted(indexes, key=lambda x: x["name"]),
                }
            return tables
        finally:
            connection.close()


def build_contract() -> dict[str, object]:
    public_exports = sorted(getattr(trustflow, "__all__", ()))
    return {
        "contract_schema": 1,
        "release_line": "0.1",
        "policy": {
            "mode": "exact-freeze-until-v0.1.0",
            "package_version_normalized": True,
        },
        "python": {"top_level_public_exports": public_exports},
        "cli": _cli_contract(),
        "openapi": _openapi_contract(),
        "model_schemas": _model_schemas(),
        "sqlite": _sqlite_contract(),
    }


def canonical_bytes(contract: dict[str, object]) -> bytes:
    return (json.dumps(contract, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode()


def contract_lock(content: bytes) -> dict[str, object]:
    return {
        "canonical_bytes": len(content),
        "contract_schema": 1,
        "release_line": "0.1",
        "sha256": hashlib.sha256(content).hexdigest(),
    }


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_bytes(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


def main() -> None:
    parser = argparse.ArgumentParser()
    output_group = parser.add_mutually_exclusive_group()
    output_group.add_argument(
        "--write",
        action="store_true",
        help="Explicitly replace the frozen contract lock with the current canonical digest.",
    )
    output_group.add_argument(
        "--emit",
        type=Path,
        help=(
            "Write the full current canonical contract to a review artifact without changing lock."
        ),
    )
    args = parser.parse_args()

    current = canonical_bytes(build_contract())
    current_lock = contract_lock(current)
    if args.write:
        _write_json(CONTRACT_LOCK_PATH, current_lock)
        print(f"wrote {CONTRACT_LOCK_PATH}")
        return
    if args.emit is not None:
        _write_bytes(args.emit, current)
        print(f"emitted {args.emit}")
        return

    if not CONTRACT_LOCK_PATH.is_file():
        print(json.dumps(current_lock, sort_keys=True))
        raise SystemExit(f"missing frozen contract lock: {CONTRACT_LOCK_PATH}")

    try:
        expected_lock = json.loads(CONTRACT_LOCK_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"invalid frozen contract lock: {CONTRACT_LOCK_PATH}") from exc
    if expected_lock != current_lock:
        print(json.dumps(current_lock, sort_keys=True))
        raise SystemExit(
            "v0.1 compatibility surface drifted; inspect the emitted contract artifact and update "
            "the frozen lock only when the interface change is intentional"
        )
    print("v0.1 compatibility contract verified")


if __name__ == "__main__":
    main()
