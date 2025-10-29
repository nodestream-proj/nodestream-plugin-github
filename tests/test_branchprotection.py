import httpx
import pytest
from pytest_httpx import HTTPXMock
from pytest_mock import MockerFixture

from nodestream_github.client import GithubRestApiClient
from nodestream_github.client import githubclient as githubclient
from tests.mocks.githubrest import DEFAULT_BASE_URL, DEFAULT_HOSTNAME


@pytest.mark.asyncio
async def test_fetch_branch_protection(httpx_mock: HTTPXMock):
    client = GithubRestApiClient(
        auth_token="test-auth-token",
        github_hostname=DEFAULT_HOSTNAME,
        user_agent="test-user-agent",
    )

    httpx_mock.add_response(
        url=f"{DEFAULT_BASE_URL}/repos/octocat/Hello-World/branches/main/protection",
        json={"enabled": True},
    )

    result = await client.fetch_branch_protection(
        owner_login="octocat",
        repo_name="Hello-World",
        branch="main",
    )

    assert result == {"enabled": True}


@pytest.mark.asyncio
async def test_fetch_branch_protection_404(
    httpx_mock: HTTPXMock, mocker: MockerFixture
):
    client = GithubRestApiClient(
        auth_token="test-auth-token",
        github_hostname=DEFAULT_HOSTNAME,
        user_agent="test-user-agent",
    )

    httpx_mock.add_response(
        url=f"{DEFAULT_BASE_URL}/repos/octocat/Hello-World/branches/main/protection",
        status_code=httpx.codes.NOT_FOUND,
        json={
            "documentation_url": "https://docs.github.com/enterprise-server@3.14/rest",
            "message": "Not Found",
        },
    )
    log_info = mocker.spy(githubclient.logger, "info")

    result = await client.fetch_branch_protection(
        owner_login="octocat",
        repo_name="Hello-World",
        branch="main",
    )

    assert result is None
    log_info.assert_called_once_with(
        "Branch protection not found for branch %s on repo %s/%s",
        "main",
        "octocat",
        "Hello-World",
    )


@pytest.mark.asyncio
async def test_fetch_branch_protection_503(
    httpx_mock: HTTPXMock, mocker: MockerFixture
):
    client = GithubRestApiClient(
        auth_token="test-auth-token",
        github_hostname=DEFAULT_HOSTNAME,
        user_agent="test-user-agent",
    )

    httpx_mock.add_response(
        url=f"{DEFAULT_BASE_URL}/repos/octocat/Hello-World/branches/main/protection",
        status_code=httpx.codes.SERVICE_UNAVAILABLE,
    )
    log_warning = mocker.spy(githubclient.logger, "warning")

    result = await client.fetch_branch_protection(
        owner_login="octocat",
        repo_name="Hello-World",
        branch="main",
    )

    assert result is None
    log_warning.assert_called_once_with(
        "%s %s - %s%s",
        503,
        "Service Unavailable",
        "/api/v3/repos/octocat/Hello-World/branches/main/protection",
        "",
        stacklevel=2,
    )
