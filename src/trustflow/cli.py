from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from trustflow._version import __version__
from trustflow.application.bootstrap import build_service
from trustflow.demo import run_demo
from trustflow.domain.models import SourceDocument

app = typer.Typer(help="Evidence-governed RFP and security questionnaire automation.")
console = Console()


def _version(value: bool) -> None:
    if value:
        console.print(f"trustflow {__version__}")
        raise typer.Exit()


@app.callback()
def callback(
    version: Annotated[
        bool | None,
        typer.Option("--version", callback=_version, is_eager=True),
    ] = None,
) -> None:
    del version


@app.command()
def demo(directory: Annotated[Path | None, typer.Option()] = None) -> None:
    console.print_json(data=run_demo(directory))


@app.command("ingest-source")
def ingest_source(
    database: Annotated[Path, typer.Option()],
    identifier: Annotated[str, typer.Option()],
    title: Annotated[str, typer.Option()],
    owner: Annotated[str, typer.Option()],
    version: Annotated[str, typer.Option()],
    source_uri: Annotated[str, typer.Option()],
    content_file: Annotated[Path, typer.Argument(exists=True, readable=True)],
) -> None:
    service = build_service(database)
    service.ingest_source(
        SourceDocument(
            id=identifier,
            title=title,
            owner=owner,
            version=version,
            content=content_file.read_text(encoding="utf-8"),
            source_uri=source_uri,
        )
    )
    console.print("source ingested")


@app.command()
def process(
    questionnaire: Annotated[Path, typer.Argument(exists=True, readable=True)],
    output: Annotated[Path, typer.Option()],
    database: Annotated[Path, typer.Option()] = Path("trustflow.db"),
) -> None:
    service = build_service(database)
    imported = service.import_questionnaire(questionnaire)
    answers = service.draft(imported.id)
    result = service.export(imported.id, output)
    table = Table(title="TrustFlow result")
    table.add_column("Questions")
    table.add_column("Answered")
    table.add_column("Review")
    table.add_column("Unanswerable")
    table.add_row(
        str(len(answers)),
        str(result.answered),
        str(result.review_required),
        str(result.unanswerable),
    )
    console.print(table)


@app.command("impact-scan")
def impact_scan(
    database: Annotated[Path, typer.Argument(exists=True, readable=True)],
) -> None:
    service = build_service(database)
    console.print_json(data=[item.model_dump(mode="json") for item in service.impact_scan()])


@app.command("verify-audit")
def verify_audit(
    database: Annotated[Path, typer.Argument(exists=True, readable=True)],
) -> None:
    service = build_service(database)
    service.verify_audit()
    console.print("audit chain valid")


@app.command()
def serve(
    database: Annotated[str, typer.Option()] = "trustflow.db",
    host: Annotated[str, typer.Option()] = "127.0.0.1",
    port: Annotated[int, typer.Option()] = 8081,
) -> None:
    try:
        import uvicorn
    except ImportError as exc:
        raise typer.BadParameter("Install with: pip install 'trustflow[web]'") from exc
    uvicorn.run("trustflow.web.app:create_app", factory=True, host=host, port=port)
