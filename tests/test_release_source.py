import pytest
from scripts import check_release


def test_release_rejects_wrong_tag() -> None:
    with pytest.raises(SystemExit, match="tag mismatch"):
        check_release.validate_release("v9.9.9", require_main_tip=False)


def test_release_rejects_non_main_tip(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_git(*args: str) -> str:
        if args == ("rev-parse", "HEAD"):
            return "candidate"
        if args == ("rev-parse", "refs/remotes/origin/main"):
            return "main"
        raise AssertionError(args)

    monkeypatch.setattr(check_release, "_git", fake_git)
    with pytest.raises(SystemExit, match="not current main tip"):
        check_release.validate_release("v0.1.0rc2", require_main_tip=True)


def test_release_accepts_exact_main_tip(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_git(*args: str) -> str:
        if args in {
            ("rev-parse", "HEAD"),
            ("rev-parse", "refs/remotes/origin/main"),
        }:
            return "same-commit"
        if args == ("status", "--porcelain", "--untracked-files=all"):
            return ""
        raise AssertionError(args)

    monkeypatch.setattr(check_release, "_git", fake_git)
    assert check_release.validate_release("v0.1.0rc2", require_main_tip=True) == "v0.1.0rc2"
