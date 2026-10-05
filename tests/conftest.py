import pytest
from pytest_httpx2 import HTTPXMock

from nodestream_github.client import GithubRestApiClient
from tests.mocks.githubrest import DEFAULT_HOSTNAME, GithubHttpxMock


@pytest.fixture
def gh_rest_mock(httpx2_mock: HTTPXMock) -> GithubHttpxMock:
    return GithubHttpxMock(httpx2_mock)


@pytest.fixture
def core_client() -> GithubRestApiClient:
    return GithubRestApiClient(
        auth_token="test-auth-token",
        github_hostname=DEFAULT_HOSTNAME,
        user_agent="test-user-agent",
    )
