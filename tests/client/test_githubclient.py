import time
from typing import Any
from unittest.mock import AsyncMock

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
async def test_exhausted_limiter_is_logged_and_skipped(
    httpx_mock: HTTPXMock, caplog: pytest.LogCaptureFixture
):
    client = GithubRestApiClient(
        auth_token="test-auth-token",
        github_hostname=DEFAULT_HOSTNAME,
        user_agent="test-user-agent",
        max_retries=2,
        max_retry_wait_seconds=0,
        rate_limit_per_minute=1,
    )
    url = f"{DEFAULT_BASE_URL}/users/octocat"
    httpx_mock.add_response(url=url, json={"login": "octocat"})

    assert await client.fetch_user(username="octocat") == {"login": "octocat"}
    with caplog.at_level("WARNING"):
        assert await client.fetch_user(username="octocat") is None

    # The retry library logs its own warnings on the same logger. Count only ours.
    gave_up = [r for r in caplog.records if r.getMessage().startswith("Gave up")]
    assert len(gave_up) == 1
    assert url in gave_up[0].getMessage()
    assert gave_up[0].exc_info is None


EXAMPLE_URL = f"{DEFAULT_BASE_URL}/example?per_page=100"
RATE_LIMIT_MESSAGE = {"message": "API rate limit exceeded for user ID 1"}


def _client_with_fake_sleep(**kwargs: Any) -> GithubRestApiClient:
    """Build a client whose retryer records sleeps instead of waiting."""
    options = {
        "auth_token": "test-auth-token",
        "github_hostname": DEFAULT_HOSTNAME,
        "user_agent": "test-user-agent",
    } | kwargs
    client = GithubRestApiClient(**options)
    client.retryer.sleep = AsyncMock()
    return client


def _slept(client: GithubRestApiClient) -> list[float]:
    return [call.args[0] for call in client.retryer.sleep.await_args_list]


@pytest.mark.parametrize(
    ("status_code", "headers", "body"),
    [
        pytest.param(403, {"x-ratelimit-remaining": "0"}, {}, id="403-remaining-zero"),
        pytest.param(403, {"retry-after": "1"}, {}, id="403-retry-after"),
        pytest.param(403, {}, RATE_LIMIT_MESSAGE, id="403-primary-message-only"),
        pytest.param(
            403,
            {},
            {"message": "You have exceeded a secondary rate limit."},
            id="403-secondary-message-only",
        ),
        pytest.param(429, {}, {}, id="429-bare"),
    ],
)
@pytest.mark.asyncio
async def test_server_rate_limit_is_retried(
    httpx_mock: HTTPXMock, status_code: int, headers: dict, body: dict
):
    client = _client_with_fake_sleep(max_retries=3)
    httpx_mock.add_response(
        url=EXAMPLE_URL,
        status_code=status_code,
        headers=headers,
        json=body,
        is_reusable=False,
    )
    httpx_mock.add_response(url=EXAMPLE_URL, json=["a"], is_reusable=False)

    items = [item async for item in client._get_paginated("example")]

    assert items == ["a"]
    assert len(_slept(client)) == 1


@pytest.mark.parametrize(
    ("headers", "body"),
    [
        pytest.param(
            {"x-ratelimit-remaining": "4999"},
            {"message": "Resource not accessible by personal access token"},
            id="permission-message",
        ),
        pytest.param({}, {}, id="json-body-without-message"),
        pytest.param({}, {"errors": []}, id="json-body-with-other-keys"),
    ],
)
@pytest.mark.asyncio
async def test_permission_failure_is_not_retried(
    httpx_mock: HTTPXMock, headers: dict, body: dict
):
    client = _client_with_fake_sleep(max_retries=3)
    httpx_mock.add_response(
        url=EXAMPLE_URL, status_code=403, headers=headers, json=body
    )

    with pytest.raises(httpx.HTTPStatusError):
        _ignored = [item async for item in client._get_paginated("example")]

    assert _slept(client) == []


@pytest.mark.asyncio
async def test_permission_failure_with_plain_text_body_is_not_retried(
    httpx_mock: HTTPXMock,
):
    client = _client_with_fake_sleep(max_retries=3)
    httpx_mock.add_response(url=EXAMPLE_URL, status_code=403, text="Forbidden")

    with pytest.raises(httpx.HTTPStatusError):
        _ignored = [item async for item in client._get_paginated("example")]

    assert _slept(client) == []


@pytest.mark.asyncio
async def test_rate_limit_waits_for_stated_reset(httpx_mock: HTTPXMock):
    client = _client_with_fake_sleep(max_retries=3)
    reset = int(time.time()) + 40 * 60
    httpx_mock.add_response(
        url=EXAMPLE_URL,
        status_code=403,
        headers={"x-ratelimit-remaining": "0", "x-ratelimit-reset": str(reset)},
        json=RATE_LIMIT_MESSAGE,
        is_reusable=False,
    )
    httpx_mock.add_response(url=EXAMPLE_URL, json=["a"], is_reusable=False)

    items = [item async for item in client._get_paginated("example")]

    assert items == ["a"]
    (slept,) = _slept(client)
    assert 2395 <= slept <= 2432  # 40 minutes plus jitter of up to 30 seconds


@pytest.mark.asyncio
async def test_rate_limit_waits_for_retry_after(httpx_mock: HTTPXMock):
    client = _client_with_fake_sleep(max_retries=3)
    httpx_mock.add_response(
        url=EXAMPLE_URL,
        status_code=429,
        headers={"retry-after": "120"},
        is_reusable=False,
    )
    httpx_mock.add_response(url=EXAMPLE_URL, json=["a"], is_reusable=False)

    [item async for item in client._get_paginated("example")]

    (slept,) = _slept(client)
    assert 120 <= slept <= 150


@pytest.mark.asyncio
async def test_rate_limit_with_past_reset_waits_only_jitter(httpx_mock: HTTPXMock):
    client = _client_with_fake_sleep(max_retries=3)
    httpx_mock.add_response(
        url=EXAMPLE_URL,
        status_code=403,
        headers={
            "x-ratelimit-remaining": "0",
            "x-ratelimit-reset": str(int(time.time()) - 10),
        },
        is_reusable=False,
    )
    httpx_mock.add_response(url=EXAMPLE_URL, json=["a"], is_reusable=False)

    [item async for item in client._get_paginated("example")]

    (slept,) = _slept(client)
    assert 0 <= slept <= 30


@pytest.mark.parametrize("max_retry_wait_seconds", [0, 300])
@pytest.mark.asyncio
async def test_rate_limit_without_stated_wait_waits_at_least_a_minute(
    httpx_mock: HTTPXMock, max_retry_wait_seconds: int
):
    client = _client_with_fake_sleep(
        max_retries=3, max_retry_wait_seconds=max_retry_wait_seconds
    )
    httpx_mock.add_response(
        url=EXAMPLE_URL, status_code=403, json=RATE_LIMIT_MESSAGE, is_reusable=False
    )
    httpx_mock.add_response(url=EXAMPLE_URL, json=["a"], is_reusable=False)

    [item async for item in client._get_paginated("example")]

    (slept,) = _slept(client)
    assert slept >= 60


@pytest.mark.parametrize("retry_after", ["100000", "abc"])
@pytest.mark.asyncio
async def test_unusable_stated_wait_counts_as_not_stated(
    httpx_mock: HTTPXMock, retry_after: str
):
    client = _client_with_fake_sleep(max_retries=3, max_retry_wait_seconds=300)
    httpx_mock.add_response(
        url=EXAMPLE_URL,
        status_code=403,
        headers={"retry-after": retry_after},
        is_reusable=False,
    )
    httpx_mock.add_response(url=EXAMPLE_URL, json=["a"], is_reusable=False)

    [item async for item in client._get_paginated("example")]

    (slept,) = _slept(client)
    assert 60 <= slept <= 300


@pytest.mark.asyncio
async def test_own_limiter_block_keeps_exponential_wait(httpx_mock: HTTPXMock):
    client = _client_with_fake_sleep(
        max_retries=3, max_retry_wait_seconds=300, rate_limit_per_minute=1
    )
    httpx_mock.add_response(url=EXAMPLE_URL, json=["a"])

    [item async for item in client._get_paginated("example")]
    with pytest.raises(RateLimitedError):
        [item async for item in client._get_paginated("example")]

    # Two sleeps for three attempts. The exponential bound is 1 then 2 seconds.
    assert len(_slept(client)) == 2
    assert all(slept < 60 for slept in _slept(client))


@pytest.mark.asyncio
async def test_server_rate_limit_past_max_retries_raises(httpx_mock: HTTPXMock):
    client = _client_with_fake_sleep(max_retries=2)
    for _ in range(2):
        httpx_mock.add_response(
            url=EXAMPLE_URL,
            status_code=403,
            json=RATE_LIMIT_MESSAGE,
            is_reusable=False,
        )

    with pytest.raises(RateLimitedError) as exc_info:
        [item async for item in client._get_paginated("example")]

    assert exc_info.value.from_server is True


@pytest.mark.asyncio
async def test_server_rate_limit_past_max_retries_is_logged_and_skipped(
    httpx_mock: HTTPXMock, caplog: pytest.LogCaptureFixture
):
    client = _client_with_fake_sleep(max_retries=2)
    url = f"{DEFAULT_BASE_URL}/users/octocat"
    for _ in range(2):
        httpx_mock.add_response(
            url=url, status_code=403, json=RATE_LIMIT_MESSAGE, is_reusable=False
        )

    with caplog.at_level("WARNING"):
        assert await client.fetch_user(username="octocat") is None

    gave_up = [r for r in caplog.records if r.getMessage().startswith("Gave up")]
    assert len(gave_up) == 1


@pytest.mark.asyncio
async def test_rate_limit_on_later_page_retries_only_that_page(
    httpx_mock: HTTPXMock,
):
    client = _client_with_fake_sleep(max_retries=3, per_page=2)
    page_one = f"{DEFAULT_BASE_URL}/example?per_page=2"
    page_two = f"{DEFAULT_BASE_URL}/example?per_page=2&page=2"
    httpx_mock.add_response(
        url=page_one,
        json=["a", "b"],
        headers={"link": f'<{page_two}>; rel="next"'},
        is_reusable=False,
    )
    httpx_mock.add_response(
        url=page_two, status_code=403, json=RATE_LIMIT_MESSAGE, is_reusable=False
    )
    httpx_mock.add_response(url=page_two, json=["c", "d"], is_reusable=False)

    items = [item async for item in client._get_paginated("example")]

    assert items == ["a", "b", "c", "d"]
    assert len(_slept(client)) == 1


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
