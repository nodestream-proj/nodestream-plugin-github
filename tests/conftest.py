import pytest
from pytest_httpx import HTTPXMock

from nodestream_github.client import GithubRestApiClient
from tests.mocks.githubrest import DEFAULT_HOSTNAME, GithubHttpxMock


@pytest.fixture
def gh_rest_mock(httpx_mock: HTTPXMock) -> GithubHttpxMock:
    return GithubHttpxMock(httpx_mock)


@pytest.fixture
def core_client() -> GithubRestApiClient:
    return GithubRestApiClient(
        auth_token="test-auth-token",
        github_hostname=DEFAULT_HOSTNAME,
        user_agent="test-user-agent",
    )
