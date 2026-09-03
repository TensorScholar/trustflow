from pathlib import Path

import pytest
import typer

from trustflow.cli import _is_loopback_host, serve


def test_loopback_host_detection_is_fail_closed() -> None:
    assert _is_loopback_host("127.0.0.1")
    assert _is_loopback_host("::1")
    assert _is_loopback_host("localhost")
    assert not _is_loopback_host("0.0.0.0")  # noqa: S104 - intentional unsafe-bind fixture
    assert not _is_loopback_host("example.com")


def test_serve_rejects_non_loopback_without_explicit_opt_in(tmp_path) -> None:
    with pytest.raises(typer.BadParameter, match="non-loopback API binding is disabled"):
        serve(
            database=Path(tmp_path / "web.db"),
            upload_dir=Path(tmp_path / "uploads"),
            host="0.0.0.0",  # noqa: S104 - intentional unsafe-bind fixture
            port=8081,
            allow_unsafe_remote=False,
        )
