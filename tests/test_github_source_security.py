from unittest.mock import MagicMock, patch

from trustflow.adapters.github_source import GitHubEvidenceSource


def test_github_connector_ignores_ambient_proxy_environment() -> None:
    client_instance = MagicMock()
    with patch(
        "trustflow.adapters.github_source.httpx.Client",
        return_value=client_instance,
    ) as client_factory:
        connector = GitHubEvidenceSource(token="github-test-token")
        connector.close()

    assert client_factory.call_args.kwargs["trust_env"] is False
    assert client_factory.call_args.kwargs["follow_redirects"] is False
    client_instance.close.assert_called_once_with()
