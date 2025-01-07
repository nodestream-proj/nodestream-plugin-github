import httpx
import pytest
from pytest_httpx import HTTPXMock

from nodestream_github.util.githubclient import (
    GithubRestApiClient,
    RateLimitedException,
)
from tests.mocks.githubrest import DEFAULT_ENDPOINT

# @pytest.fixture
# def github_client():
#     return GithubRestApiClient(auth_token="test-auth-token", github_endpoint=DEFAULT_ENDPOINT, user_agent="test-user-agent", max_retries=2)


@pytest.mark.parametrize("status_code", [400, 401, 420, 500, 502, 503])
@pytest.mark.asyncio
async def test_do_not_retry_bad_status(httpx_mock: HTTPXMock, status_code):
    client = GithubRestApiClient(
        auth_token="test-auth-token",
        github_endpoint=DEFAULT_ENDPOINT,
        user_agent="test-user-agent",
        max_retries=2,
    )

    httpx_mock.add_response(
        url=f"{DEFAULT_ENDPOINT}/example?per_page=100", status_code=status_code
    )

    with pytest.raises(httpx.HTTPStatusError):
        [item async for item in client.get("example")]


@pytest.mark.asyncio
async def test_retry_ratelimited(httpx_mock: HTTPXMock):
    client = GithubRestApiClient(
        auth_token="test-auth-token",
        github_endpoint=DEFAULT_ENDPOINT,
        user_agent="test-user-agent",
        max_retries=2,
        request_rate_limit=1,
    )

    httpx_mock.add_response(
        url=f"{DEFAULT_ENDPOINT}/example?per_page=100", status_code=200, json=["a", "b"]
    )

    with pytest.raises(RateLimitedException):
        for _ in range(100):
            [item async for item in client.get("example")]


@pytest.mark.asyncio
async def test_pagination(httpx_mock: HTTPXMock):
    client = GithubRestApiClient(
        auth_token="test-auth-token",
        github_endpoint=DEFAULT_ENDPOINT,
        user_agent="test-user-agent",
        max_retries=0,
        page_size=2,
    )

    httpx_mock.add_response(
        url=f"{DEFAULT_ENDPOINT}/example?per_page=2",
        status_code=200,
        json=["a", "b"],
        is_reusable=False,
        headers={
            "link": f'<{DEFAULT_ENDPOINT}/example?per_page=2&page=1>; rel="next", <${DEFAULT_ENDPOINT}/example?per_page=2>; rel="first"'
        },
    )
    httpx_mock.add_response(
        url=f"{DEFAULT_ENDPOINT}/example?per_page=2&page=1",
        status_code=200,
        json=["c", "d"],
        is_reusable=False,
    )

    items = [item async for item in client.get("example")]
    assert items == ["a", "b", "c", "d"]
