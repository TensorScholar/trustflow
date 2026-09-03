"""Freeze and verify the TrustFlow v0.1 release-candidate compatibility surface."""

from __future__ import annotations

import argparse
import base64
import json
import sqlite3
import tempfile
import zlib
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

CONTRACT_PATH = Path("compatibility/v0.1-contract.json")


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
    if not isinstance(command, click.Group):
        raise RuntimeError("TrustFlow CLI root is not a Click group")
    return {
        "root_params": [_click_param(param) for param in command.params],
        "commands": {
            name: {
                "params": [_click_param(param) for param in child.params],
            }
            for name, child in sorted(command.commands.items())
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


def _bootstrap_payload(content: bytes) -> str:
    return base64.b64encode(zlib.compress(content, level=9)).decode("ascii")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--write",
        action="store_true",
        help="Explicitly replace the frozen contract baseline with the current surface.",
    )
    args = parser.parse_args()

    current = canonical_bytes(build_contract())
    if args.write:
        CONTRACT_PATH.parent.mkdir(parents=True, exist_ok=True)
        CONTRACT_PATH.write_bytes(current)
        print(f"wrote {CONTRACT_PATH}")
        return

    if not CONTRACT_PATH.is_file():
        print(f"CONTRACT_BASE64_ZLIB={_bootstrap_payload(current)}")
        raise SystemExit(f"missing frozen contract: {CONTRACT_PATH}")

    expected = CONTRACT_PATH.read_bytes()
    if expected != current:
        print(f"CONTRACT_BASE64_ZLIB={_bootstrap_payload(current)}")
        raise SystemExit(
            "v0.1 compatibility surface drifted; inspect the change and update the frozen contract "
            "only when the interface change is intentional"
        )
    print("v0.1 compatibility contract verified")


if __name__ == "__main__":
    main()
