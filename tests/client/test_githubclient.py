import httpx2
import pytest
from pytest_httpx2 import HTTPXMock

from nodestream_github.client.rest.githubclient import (
    GithubRestApiClient,
    RateLimitedError,
)
from tests.mocks.githubrest import DEFAULT_BASE_URL, DEFAULT_HOSTNAME


@pytest.mark.parametrize(
    "status_code",
    [
        httpx2.codes.BAD_REQUEST,
        httpx2.codes.UNAUTHORIZED,
        420,
        httpx2.codes.INTERNAL_SERVER_ERROR,
        httpx2.codes.BAD_GATEWAY,
        httpx2.codes.SERVICE_UNAVAILABLE,
        httpx2.codes.GATEWAY_TIMEOUT,
    ],
)
@pytest.mark.asyncio
async def test_retry_bad_status(httpx2_mock: HTTPXMock, status_code: int):
    client = GithubRestApiClient(
        auth_token="test-auth-token",
        github_hostname=DEFAULT_HOSTNAME,
        user_agent="test-user-agent",
        max_retries=5,
        max_retry_wait_seconds=0,
    )

    httpx2_mock.add_response(
        url=f"{DEFAULT_BASE_URL}/example?per_page=100",
        status_code=status_code,
        is_reusable=False,
    )

    with pytest.raises(httpx2.HTTPStatusError):
        _ignore = [item async for item in client.get_paginated("example")]


@pytest.mark.asyncio
async def test_retry_ratelimited(httpx2_mock: HTTPXMock):
    client = GithubRestApiClient(
        auth_token="test-auth-token",
        github_hostname=DEFAULT_HOSTNAME,
        user_agent="test-user-agent",
        max_retries=2,
        rate_limit_per_minute=1,
    )

    httpx2_mock.add_response(
        url=f"{DEFAULT_BASE_URL}/example?per_page=100", json=["a", "b"]
    )

    _ignored = [item async for item in client.get_paginated("example")]
    with pytest.raises(RateLimitedError):
        _ignored = [item async for item in client.get_paginated("example")]


@pytest.mark.asyncio
async def test_pagination(httpx2_mock: HTTPXMock):
    client = GithubRestApiClient(
        auth_token="test-auth-token",
        github_hostname=DEFAULT_HOSTNAME,
        user_agent="test-user-agent",
        max_retries=0,
        per_page=2,
    )
    next_page = f'<{DEFAULT_BASE_URL}/example?per_page=2&page=1>; rel="next"'
    first_page = f'<${DEFAULT_BASE_URL}/example?per_page=2&page=0>; rel="first"'
    httpx2_mock.add_response(
        url=f"{DEFAULT_BASE_URL}/example?per_page=2",
        json=["a", "b"],
        is_reusable=False,
        headers={"link": f"{next_page}, {first_page}"},
    )
    httpx2_mock.add_response(
        url=f"{DEFAULT_BASE_URL}/example?per_page=2&page=1",
        json=["c", "d"],
        is_reusable=False,
    )

    items = [item async for item in client.get_paginated("example")]
    assert items == ["a", "b", "c", "d"]


@pytest.mark.asyncio
async def test_pagination_truncate_warning(
    httpx2_mock: HTTPXMock, caplog: pytest.LogCaptureFixture
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
    httpx2_mock.add_response(
        url=f"{DEFAULT_BASE_URL}/example?per_page=2",
        json=["a", "b"],
        is_reusable=False,
        headers={"link": f"{next_page}, {first_page}"},
    )
    httpx2_mock.add_response(
        url=f"{DEFAULT_BASE_URL}/example?per_page=2&page=100",
        json=["c", "d"],
        is_reusable=False,
    )

    with caplog.at_level("INFO"):
        items = [item async for item in client.get_paginated("example")]

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
