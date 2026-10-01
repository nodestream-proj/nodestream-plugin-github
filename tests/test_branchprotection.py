import logging

import httpx
import pytest
from pytest_httpx import HTTPXMock

from nodestream_github.client import GithubRestApiClient
from nodestream_github.client.rest.repoclient import RepoClient
from tests.mocks.githubrest import DEFAULT_BASE_URL


@pytest.mark.asyncio
async def test_fetch_branch_protection(
    httpx_mock: HTTPXMock, core_client: GithubRestApiClient
):
    client = RepoClient(core_client)

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
    httpx_mock: HTTPXMock,
    caplog: pytest.LogCaptureFixture,
    core_client: GithubRestApiClient,
):
    client = RepoClient(core_client)

    httpx_mock.add_response(
        url=f"{DEFAULT_BASE_URL}/repos/octocat/Hello-World/branches/main/protection",
        status_code=httpx.codes.NOT_FOUND,
        json={
            "documentation_url": "https://docs.github.com/enterprise-server@3.14/rest",
            "message": "Not Found",
        },
    )
    with caplog.at_level(logging.INFO):
        result = await client.fetch_branch_protection(
            owner_login="octocat",
            repo_name="Hello-World",
            branch="main",
        )

        assert result is None
        assert (
            "nodestream_github.client.rest.repoclient",
            logging.INFO,
            "Branch protection not found for branch main on repo octocat/Hello-World",
        ) in caplog.record_tuples


@pytest.mark.asyncio
async def test_fetch_branch_protection_503(
    httpx_mock: HTTPXMock,
    caplog: pytest.LogCaptureFixture,
    core_client: GithubRestApiClient,
):
    client = RepoClient(core_client)

    httpx_mock.add_response(
        url=f"{DEFAULT_BASE_URL}/repos/octocat/Hello-World/branches/main/protection",
        status_code=httpx.codes.SERVICE_UNAVAILABLE,
    )

    with caplog.at_level(logging.WARNING):
        result = await client.fetch_branch_protection(
            owner_login="octocat",
            repo_name="Hello-World",
            branch="main",
        )

        assert result is None
        assert (
            "nodestream_github.client.rest.githubclient",
            logging.WARNING,
            "503 Service Unavailable - "
            "/api/v3/repos/octocat/Hello-World/branches/main/protection",
        ) in caplog.record_tuples
