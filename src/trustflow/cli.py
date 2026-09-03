from __future__ import annotations

import os
from ipaddress import ip_address
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from trustflow._version import __version__
from trustflow.application.bootstrap import build_service
from trustflow.demo import run_demo
from trustflow.domain.errors import InvalidTransitionError, TrustFlowError
from trustflow.domain.models import ReviewState, SourceClassification, SourceDocument

app = typer.Typer(help="Evidence-governed RFP and security questionnaire automation.")
console = Console()


def _version(value: bool) -> None:
    if value:
        console.print(f"trustflow {__version__}")
        raise typer.Exit()


def _is_loopback_host(host: str) -> bool:
    candidate = host.strip().removeprefix("[").removesuffix("]")
    if candidate.casefold() == "localhost":
        return True
    try:
        return ip_address(candidate).is_loopback
    except ValueError:
        return False


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


@app.command("ingest-github-source")
def ingest_github_source(
    database: Annotated[Path, typer.Option()],
    identifier: Annotated[str, typer.Option()],
    title: Annotated[str, typer.Option()],
    owner: Annotated[str, typer.Option(help="Governance owner for the evidence source.")],
    repository: Annotated[str, typer.Option(help="Explicit GitHub repository as owner/name.")],
    path: Annotated[str, typer.Option(help="Exact UTF-8 repository file path.")],
    ref: Annotated[str, typer.Option(help="Branch, tag, or commit to resolve and pin.")],
    classification: Annotated[SourceClassification, typer.Option()] = SourceClassification.INTERNAL,
    approved: Annotated[
        bool,
        typer.Option(
            "--approved/--unapproved",
            help="Explicitly approve this source for retrieval. Defaults to unapproved.",
        ),
    ] = False,
    maximum_file_bytes: Annotated[int, typer.Option(min=1, max=1_000_000)] = 1_000_000,
) -> None:
    token = os.environ.get("TRUSTFLOW_GITHUB_TOKEN", "")
    if not token:
        raise typer.BadParameter(
            "set TRUSTFLOW_GITHUB_TOKEN; tokens are never accepted as CLI args"
        )
    try:
        from trustflow.adapters.github_source import GitHubEvidenceSource
    except ImportError as exc:
        raise typer.BadParameter("Install with: pip install 'trustflow[github]'") from exc

    service = build_service(database)
    try:
        with GitHubEvidenceSource(
            token=token,
            maximum_file_bytes=maximum_file_bytes,
        ) as connector:
            source = connector.load_file(
                repository=repository,
                path=path,
                ref=ref,
                identifier=identifier,
                title=title,
                evidence_owner=owner,
                classification=classification,
                approved=approved,
            )
        service.ingest_source(source)
    except TrustFlowError as exc:
        raise typer.BadParameter(str(exc)) from exc
    console.print(f"GitHub source ingested at immutable commit {source.version}")


@app.command()
def process(
    questionnaire: Annotated[Path, typer.Argument(exists=True, readable=True)],
    output: Annotated[Path, typer.Option()],
    database: Annotated[Path, typer.Option()] = Path("trustflow.db"),
) -> None:
    service = build_service(database)
    imported = service.import_questionnaire(questionnaire)
    answers = service.draft(imported.id)
    table = Table(title="TrustFlow draft result")
    table.add_column("Questions")
    table.add_column("Answered")
    table.add_column("Review")
    table.add_column("Unanswerable")
    table.add_row(
        str(len(answers)),
        str(sum(item.status.value == "answered" for item in answers)),
        str(sum(item.status.value in {"review_required", "conflict"} for item in answers)),
        str(sum(item.status.value in {"unanswerable", "stale"} for item in answers)),
    )
    console.print(table)
    try:
        result = service.export(imported.id, output)
    except InvalidTransitionError as exc:
        console.print(f"[red]Export blocked:[/red] {exc}")
        console.print("Review unresolved answers, then use the export command.")
        raise typer.Exit(code=2) from exc
    console.print(f"exported to {result.output_path}")


@app.command("review-answer")
def review_answer(
    database: Annotated[Path, typer.Option(exists=True, readable=True)],
    answer_id: Annotated[str, typer.Argument()],
    reviewer: Annotated[str, typer.Option()],
    state: Annotated[ReviewState, typer.Option()] = ReviewState.APPROVED,
    final_text: Annotated[str, typer.Option()] = "",
    note: Annotated[str, typer.Option()] = "",
) -> None:
    service = build_service(database)
    review = service.review(
        answer_id,
        reviewer=reviewer,
        state=state,
        final_text=final_text,
        note=note,
    )
    console.print_json(data=review.model_dump(mode="json"))


@app.command("export")
def export_questionnaire(
    database: Annotated[Path, typer.Option(exists=True, readable=True)],
    questionnaire_id: Annotated[str, typer.Argument()],
    output: Annotated[Path, typer.Option()],
) -> None:
    service = build_service(database)
    result = service.export(questionnaire_id, output)
    console.print_json(data=result.model_dump(mode="json"))


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
    database: Annotated[Path, typer.Option()] = Path("trustflow.db"),
    upload_dir: Annotated[Path, typer.Option()] = Path(".trustflow/uploads"),
    host: Annotated[str, typer.Option()] = "127.0.0.1",
    port: Annotated[int, typer.Option(min=1, max=65535)] = 8081,
    allow_unsafe_remote: Annotated[
        bool,
        typer.Option(
            "--allow-unsafe-remote",
            help=(
                "Explicitly allow the unauthenticated evaluation API on a non-loopback host. "
                "Do not use for production."
            ),
        ),
    ] = False,
) -> None:
    try:
        import uvicorn

        from trustflow.web.app import create_app
    except ImportError as exc:
        raise typer.BadParameter("Install with: pip install 'trustflow[web]'") from exc

    if not _is_loopback_host(host) and not allow_unsafe_remote:
        raise typer.BadParameter(
            "non-loopback API binding is disabled; use --allow-unsafe-remote only for "
            "explicitly controlled evaluation"
        )
    if allow_unsafe_remote:
        console.print(
            "[bold red]WARNING:[/bold red] remote API access is unauthenticated and evaluation-only"
        )

    uvicorn.run(
        create_app(
            database=database,
            upload_dir=upload_dir,
            allow_remote=allow_unsafe_remote,
        ),
        host=host,
        port=port,
    )
