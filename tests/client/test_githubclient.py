import httpx
import pytest
from pytest_httpx import HTTPXMock

from nodestream_github.client.githubclient import (
    GithubRestApiClient,
    RateLimitedError,
)
from tests.mocks.githubrest import DEFAULT_BASE_URL, DEFAULT_HOSTNAME


@pytest.mark.parametrize(
    "status_code",
    [
        httpx.codes.BAD_REQUEST,
        httpx.codes.UNAUTHORIZED,
        420,
        httpx.codes.INTERNAL_SERVER_ERROR,
        httpx.codes.BAD_GATEWAY,
        httpx.codes.SERVICE_UNAVAILABLE,
        httpx.codes.GATEWAY_TIMEOUT,
    ],
)
@pytest.mark.asyncio
async def test_retry_bad_status(httpx_mock: HTTPXMock, status_code: int):
    client = GithubRestApiClient(
        auth_token="test-auth-token",
        github_hostname=DEFAULT_HOSTNAME,
        user_agent="test-user-agent",
        max_retries=5,
        max_retry_wait_seconds=0,
    )

    httpx_mock.add_response(
        url=f"{DEFAULT_BASE_URL}/example?per_page=100",
        status_code=status_code,
        is_reusable=False,
    )

    with pytest.raises(httpx.HTTPStatusError):
        _ignore = [item async for item in client._get_paginated("example")]


@pytest.mark.asyncio
async def test_retry_ratelimited(httpx_mock: HTTPXMock):
    client = GithubRestApiClient(
        auth_token="test-auth-token",
        github_hostname=DEFAULT_HOSTNAME,
        user_agent="test-user-agent",
        max_retries=2,
        rate_limit_per_minute=1,
    )

    httpx_mock.add_response(
        url=f"{DEFAULT_BASE_URL}/example?per_page=100", json=["a", "b"]
    )

    _ignored = [item async for item in client._get_paginated("example")]
    with pytest.raises(RateLimitedError):
        _ignored = [item async for item in client._get_paginated("example")]


@pytest.mark.asyncio
async def test_pagination(httpx_mock: HTTPXMock):
    client = GithubRestApiClient(
        auth_token="test-auth-token",
        github_hostname=DEFAULT_HOSTNAME,
        user_agent="test-user-agent",
        max_retries=0,
        per_page=2,
    )

    next_page = f'<{DEFAULT_BASE_URL}/example?per_page=2&page=1>; rel="next"'
    first_page = f'<${DEFAULT_BASE_URL}/example?per_page=2&page=0>; rel="first"'
    httpx_mock.add_response(
        url=f"{DEFAULT_BASE_URL}/example?per_page=2",
        json=["a", "b"],
        is_reusable=False,
        headers={"link": f"{next_page}, {first_page}"},
    )
    httpx_mock.add_response(
        url=f"{DEFAULT_BASE_URL}/example?per_page=2&page=1",
        json=["c", "d"],
        is_reusable=False,
    )

    items = [item async for item in client._get_paginated("example")]
    assert items == ["a", "b", "c", "d"]


@pytest.mark.asyncio
async def test_pagination_truncate_warning(
    httpx_mock: HTTPXMock, caplog: pytest.LogCaptureFixture
):
    client = GithubRestApiClient(
        auth_token="test-auth-token",
        github_hostname=DEFAULT_HOSTNAME,
        user_agent="test-user-agent",
        max_retries=0,
        per_page=2,
    )

    next_page = f'<{DEFAULT_BASE_URL}/example?per_page=2&page=100>; rel="next"'
    first_page = f'<${DEFAULT_BASE_URL}/example?per_page=2&page=99>; rel="first"'
    httpx_mock.add_response(
        url=f"{DEFAULT_BASE_URL}/example?per_page=2",
        json=["a", "b"],
        is_reusable=False,
        headers={"link": f"{next_page}, {first_page}"},
    )
    httpx_mock.add_response(
        url=f"{DEFAULT_BASE_URL}/example?per_page=2&page=100",
        json=["c", "d"],
        is_reusable=False,
    )

    with caplog.at_level("WARNING"):
        items = [item async for item in client._get_paginated("example")]

    assert items == ["a", "b", "c", "d"]

    # Test that the warning message was logged
    expected_warning = (
        "The GithubAPI has reached the maximum page size of 100. "
        "The returned data may be incomplete"
    )
    assert expected_warning in caplog.text


def test_all_null_args():
    # noinspection PyTypeChecker
    assert GithubRestApiClient(auth_token=None, github_hostname=None)
