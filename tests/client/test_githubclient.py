import inspect
import logging
import time
from typing import Any, cast
from unittest.mock import AsyncMock

import httpx2
import pytest
from freezegun import freeze_time
from limits import RateLimitItemPerSecond
from pytest_httpx2 import HTTPXMock

from nodestream_github.client.rest.githubclient import (
    DEFAULT_REQUEST_RATE_LIMIT_PER_MINUTE,
    GithubRestApiClient,
    RateLimitedError,
    _pace_per_minute,
    _RateLimitState,
    _requests_per_second,
)
from nodestream_github.client.rest.userclient import UserClient
from tests.mocks.githubrest import DEFAULT_BASE_URL, DEFAULT_HOSTNAME

EXAMPLE_URL = f"{DEFAULT_BASE_URL}/example?per_page=100"
# The wording a 403 from the Intuit GHES instance carried, with placeholder IDs.
RATE_LIMIT_MESSAGE = {
    "message": (
        "API rate limit exceeded for user ID 1. If you reach out to GitHub Support "
        "for help, please include the request ID abc and timestamp "
        "2026-10-09 06:38:06 UTC."
    )
}


def _client_with_fake_sleep(**kwargs: Any) -> GithubRestApiClient:
    """Build a client whose retryer records sleeps instead of waiting."""
    options: dict[str, Any] = {
        "auth_token": "test-auth-token",
        "github_hostname": DEFAULT_HOSTNAME,
        "user_agent": "test-user-agent",
    } | kwargs
    client = GithubRestApiClient(**options)
    client.retryer.sleep = AsyncMock()
    return client


def _slept(client: GithubRestApiClient) -> list[float]:
    sleep = cast("AsyncMock", client.retryer.sleep)
    return [call.args[0] for call in sleep.await_args_list]


def _gave_up(caplog: pytest.LogCaptureFixture) -> list[logging.LogRecord]:
    # The retry library logs its own warnings on the same logger. Count only ours.
    return [r for r in caplog.records if r.getMessage().startswith("Gave up")]


def _fail_once_then_succeed(httpx2_mock: HTTPXMock, **failure: Any) -> None:
    httpx2_mock.add_response(url=EXAMPLE_URL, is_reusable=False, **failure)
    httpx2_mock.add_response(url=EXAMPLE_URL, json=["a"], is_reusable=False)


async def _fetch_all(client: GithubRestApiClient) -> list:
    return [item async for item in client.get_paginated("example")]


def _limit_headers(
    limit: int, remaining: int, seconds_to_reset: int, **extra: str
) -> dict[str, str]:
    return {
        "x-ratelimit-limit": str(limit),
        "x-ratelimit-remaining": str(remaining),
        "x-ratelimit-reset": str(int(time.time()) + seconds_to_reset),
    } | extra


async def _count_passes(client: GithubRestApiClient) -> int:
    """Send requests until the client's own limiter blocks one."""
    passes = 0
    for _ in range(1000):
        try:
            await _fetch_all(client)
        except RateLimitedError:
            break
        passes += 1
    return passes


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
        max_retry_wait_seconds=0,
        rate_limit_per_minute=1,
    )

    httpx2_mock.add_response(
        url=f"{DEFAULT_BASE_URL}/example?per_page=100", json=["a", "b"]
    )

    _ignored = [item async for item in client.get_paginated("example")]
    with pytest.raises(RateLimitedError):
        _ignored = [item async for item in client.get_paginated("example")]


@pytest.mark.asyncio
async def test_exhausted_limiter_is_logged_and_skipped(
    httpx2_mock: HTTPXMock, caplog: pytest.LogCaptureFixture
):
    client = _client_with_fake_sleep(max_retries=2, rate_limit_per_minute=1)
    url = f"{DEFAULT_BASE_URL}/users/octocat"
    httpx2_mock.add_response(url=url, json={"login": "octocat"})

    assert await UserClient(client).fetch_user(username="octocat") == {
        "login": "octocat"
    }
    with caplog.at_level("WARNING"):
        assert await UserClient(client).fetch_user(username="octocat") is None

    (gave_up,) = _gave_up(caplog)
    assert url in gave_up.getMessage()
    assert gave_up.exc_info is None
    # The client's own pacing retries log at debug. Only the give-up line warns.
    assert [r for r in caplog.records if r.levelno >= logging.WARNING] == [gave_up]


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
    httpx2_mock: HTTPXMock, status_code: int, headers: dict, body: dict
):
    client = _client_with_fake_sleep(max_retries=3)
    _fail_once_then_succeed(
        httpx2_mock, status_code=status_code, headers=headers, json=body
    )

    assert await _fetch_all(client) == ["a"]
    assert len(_slept(client)) == 1


@pytest.mark.parametrize(
    "response",
    [
        pytest.param(
            {
                "status_code": 403,
                "headers": {"x-ratelimit-remaining": "4999"},
                "json": {"message": "Resource not accessible by personal access token"},
            },
            id="permission-message",
        ),
        pytest.param({"status_code": 403, "json": {}}, id="json-body-without-message"),
        pytest.param(
            {"status_code": 403, "json": {"errors": []}}, id="json-body-with-other-keys"
        ),
        pytest.param({"status_code": 403, "text": "Forbidden"}, id="plain-text-body"),
    ],
)
@pytest.mark.asyncio
async def test_permission_failure_is_not_retried(
    httpx2_mock: HTTPXMock, response: dict
):
    client = _client_with_fake_sleep(max_retries=3)
    httpx2_mock.add_response(url=EXAMPLE_URL, **response)

    with pytest.raises(httpx2.HTTPStatusError):
        await _fetch_all(client)

    assert _slept(client) == []


@pytest.mark.asyncio
async def test_rate_limit_waits_for_stated_reset(httpx2_mock: HTTPXMock):
    client = _client_with_fake_sleep(max_retries=3)
    reset = int(time.time()) + 40 * 60
    _fail_once_then_succeed(
        httpx2_mock,
        status_code=403,
        headers={"x-ratelimit-remaining": "0", "x-ratelimit-reset": str(reset)},
        json=RATE_LIMIT_MESSAGE,
    )

    assert await _fetch_all(client) == ["a"]
    (slept,) = _slept(client)
    assert 2395 <= slept <= 2432  # 40 minutes plus jitter of up to 30 seconds


@pytest.mark.asyncio
async def test_rate_limit_waits_for_retry_after(httpx2_mock: HTTPXMock):
    client = _client_with_fake_sleep(max_retries=3)
    _fail_once_then_succeed(
        httpx2_mock, status_code=429, headers={"retry-after": "120"}
    )

    await _fetch_all(client)

    (slept,) = _slept(client)
    assert 120 <= slept <= 150


@pytest.mark.asyncio
async def test_rate_limit_with_past_reset_waits_only_jitter(httpx2_mock: HTTPXMock):
    client = _client_with_fake_sleep(max_retries=3)
    _fail_once_then_succeed(
        httpx2_mock,
        status_code=403,
        headers={
            "x-ratelimit-remaining": "0",
            "x-ratelimit-reset": str(int(time.time()) - 10),
        },
    )

    await _fetch_all(client)

    (slept,) = _slept(client)
    assert 0 <= slept <= 30


@pytest.mark.parametrize("max_retry_wait_seconds", [0, 300])
@pytest.mark.asyncio
async def test_rate_limit_without_stated_wait_waits_at_least_a_minute(
    httpx2_mock: HTTPXMock, max_retry_wait_seconds: int
):
    client = _client_with_fake_sleep(
        max_retries=3, max_retry_wait_seconds=max_retry_wait_seconds
    )
    _fail_once_then_succeed(httpx2_mock, status_code=403, json=RATE_LIMIT_MESSAGE)

    await _fetch_all(client)

    (slept,) = _slept(client)
    assert slept >= 60


@pytest.mark.parametrize("retry_after", ["100000", "abc"])
@pytest.mark.asyncio
async def test_unusable_stated_wait_counts_as_not_stated(
    httpx2_mock: HTTPXMock, retry_after: str
):
    client = _client_with_fake_sleep(max_retries=3, max_retry_wait_seconds=300)
    _fail_once_then_succeed(
        httpx2_mock, status_code=403, headers={"retry-after": retry_after}
    )

    await _fetch_all(client)

    (slept,) = _slept(client)
    assert 60 <= slept <= 300


@pytest.mark.asyncio
async def test_own_limiter_block_keeps_exponential_wait(httpx2_mock: HTTPXMock):
    client = _client_with_fake_sleep(
        max_retries=3, max_retry_wait_seconds=300, rate_limit_per_minute=1
    )
    httpx2_mock.add_response(url=EXAMPLE_URL, json=["a"])

    await _fetch_all(client)
    with pytest.raises(RateLimitedError):
        await _fetch_all(client)

    # Two sleeps for three attempts. The exponential bound is 1 then 2 seconds.
    assert len(_slept(client)) == 2
    assert all(slept < 60 for slept in _slept(client))


@pytest.mark.asyncio
async def test_server_rate_limit_past_max_retries_raises(httpx2_mock: HTTPXMock):
    client = _client_with_fake_sleep(max_retries=2)
    for _ in range(2):
        httpx2_mock.add_response(
            url=EXAMPLE_URL,
            status_code=403,
            json=RATE_LIMIT_MESSAGE,
            is_reusable=False,
        )

    with pytest.raises(RateLimitedError) as exc_info:
        await _fetch_all(client)

    assert exc_info.value.from_server is True


@pytest.mark.asyncio
async def test_server_rate_limit_past_max_retries_is_logged_and_skipped(
    httpx2_mock: HTTPXMock, caplog: pytest.LogCaptureFixture
):
    client = _client_with_fake_sleep(max_retries=2)
    url = f"{DEFAULT_BASE_URL}/users/octocat"
    for _ in range(2):
        httpx2_mock.add_response(
            url=url, status_code=403, json=RATE_LIMIT_MESSAGE, is_reusable=False
        )

    with caplog.at_level("WARNING"):
        assert await UserClient(client).fetch_user(username="octocat") is None

    (gave_up,) = _gave_up(caplog)
    assert vars(gave_up)["status_code"] == 403


@pytest.mark.asyncio
async def test_server_rate_limit_retry_is_logged_as_warning(
    httpx2_mock: HTTPXMock, caplog: pytest.LogCaptureFixture
):
    client = _client_with_fake_sleep(max_retries=3)
    _fail_once_then_succeed(httpx2_mock, status_code=403, json=RATE_LIMIT_MESSAGE)

    with caplog.at_level("WARNING"):
        await _fetch_all(client)

    (retry,) = [
        r
        for r in caplog.records
        if r.levelno == logging.WARNING and "Retrying" in r.getMessage()
    ]
    assert "server answered 403" in retry.getMessage()
    assert vars(retry)["status_code"] == 403
    assert vars(retry)["attempt"] == 1


@pytest.mark.asyncio
async def test_rate_limit_on_later_page_retries_only_that_page(
    httpx2_mock: HTTPXMock,
):
    client = _client_with_fake_sleep(max_retries=3, per_page=2)
    page_one = f"{DEFAULT_BASE_URL}/example?per_page=2"
    page_two = f"{DEFAULT_BASE_URL}/example?per_page=2&page=2"
    httpx2_mock.add_response(
        url=page_one,
        json=["a", "b"],
        headers={"link": f'<{page_two}>; rel="next"'},
        is_reusable=False,
    )
    httpx2_mock.add_response(
        url=page_two, status_code=403, json=RATE_LIMIT_MESSAGE, is_reusable=False
    )
    httpx2_mock.add_response(url=page_two, json=["c", "d"], is_reusable=False)

    assert await _fetch_all(client) == ["a", "b", "c", "d"]
    assert len(_slept(client)) == 1


@pytest.mark.parametrize(
    ("user_cap", "limit", "remaining", "seconds_to_reset", "expected_pace"),
    [
        pytest.param(None, 5000, 5000, 3600, 75, id="full-budget"),
        pytest.param(None, 5000, 300, 1800, 9, id="budget-falling-fast"),
        pytest.param(10, 5000, 300, 1800, 9, id="user-cap-and-pace"),
        pytest.param(10, 5000, 5000, 3600, 10, id="user-cap-below-ceiling"),
        pytest.param(None, 5000, 4500, 3600, 67.5, id="pace-just-under-ceiling"),
        pytest.param(None, 60, 60, 3600, 1, id="tiny-limit"),
        pytest.param(None, 1000, 1000, 3600, 15, id="smaller-advertised-limit"),
        pytest.param(None, 5000, 0, -10, 75, id="reset-in-the-past"),
        pytest.param(None, 5000, 0, 600, 1, id="no-budget-left"),
        pytest.param(0, 5000, 5000, 3600, 0, id="zero-cap-keeps-blocking"),
        pytest.param(
            None, 150000, 137804, 2400, 2250, id="server-ceiling-over-default"
        ),
        pytest.param(None, 150000, 5000, 1800, 150, id="server-ceiling-scarce-budget"),
        pytest.param(
            216, 150000, 137804, 2400, 216, id="user-cap-below-server-ceiling"
        ),
    ],
)
def test_pace_per_minute(
    user_cap: int | None,
    limit: int,
    remaining: int,
    seconds_to_reset: int,
    expected_pace: float,
):
    now = 1_000_000
    state = _RateLimitState(limit, remaining, now + seconds_to_reset)
    assert _pace_per_minute(user_cap, state, now) == pytest.approx(expected_pace)


@pytest.mark.parametrize(
    ("user_cap", "expected_pace"),
    [
        pytest.param(None, DEFAULT_REQUEST_RATE_LIMIT_PER_MINUTE, id="default"),
        pytest.param(10, 10, id="user-cap"),
        pytest.param(0, 0, id="zero-cap"),
    ],
)
def test_pace_per_minute_without_limit_numbers(
    user_cap: int | None, expected_pace: int
):
    assert _pace_per_minute(user_cap, None, 1_000_000) == expected_pace


@pytest.mark.parametrize(
    ("pace", "expected"),
    [
        pytest.param(0, 0, id="zero-blocks"),
        pytest.param(1, 1, id="slow-pace-is-one-per-second"),
        pytest.param(9, 1, id="nine-per-minute"),
        pytest.param(60, 1, id="one-per-second"),
        pytest.param(75, 1, id="seventy-five-per-minute"),
        pytest.param(120, 2, id="two-per-second"),
        pytest.param(216, 3, id="default-pace-rounds-down"),
        pytest.param(2250, 37, id="high-pace"),
    ],
)
def test_requests_per_second(pace: float, expected: int):
    assert _requests_per_second(pace) == expected


@pytest.mark.parametrize("pace", [60, 61, 75, 119.9, 216, 777, 2250])
def test_requests_per_second_never_exceeds_the_pace(pace: float):
    assert _requests_per_second(pace) * 60 <= pace


# Each case teaches the client the limit numbers through response headers. The count is
# the window's capacity in one frozen second: the requests that pass before the
# client's own limiter blocks one.
@pytest.mark.parametrize(
    ("kwargs", "limit", "remaining", "seconds_to_reset", "expected_passes"),
    [
        pytest.param({}, 30000, 30000, 3600, 7, id="follows-advertised-limit"),
        pytest.param({}, 5000, 5000, 3600, 1, id="small-limit-is-one-per-second"),
        pytest.param({}, 5000, 300, 1800, 1, id="budget-falling-fast"),
        pytest.param({"rate_limit_per_minute": 10}, 5000, 5000, 3600, 1, id="user-cap"),
        pytest.param(
            {"rate_limit_per_minute": 216},
            150000,
            137804,
            2400,
            3,
            id="user-cap-below-server-ceiling",
        ),
        pytest.param({}, 150000, 137804, 2400, 37, id="server-ceiling-over-default"),
        pytest.param({}, 150000, 5000, 1800, 2, id="server-ceiling-scarce-budget"),
        pytest.param({}, 60, 60, 3600, 1, id="tiny-limit"),
        pytest.param({}, 5000, 0, -10, 1, id="stale-reset-keeps-ceiling"),
    ],
)
@pytest.mark.asyncio
async def test_window_admits_the_pace(
    httpx2_mock: HTTPXMock,
    kwargs: dict,
    limit: int,
    remaining: int,
    seconds_to_reset: int,
    expected_passes: int,
):
    with freeze_time(real_asyncio=True) as frozen:
        client = _client_with_fake_sleep(max_retries=1, **kwargs)
        httpx2_mock.add_response(
            url=EXAMPLE_URL,
            json=["a"],
            headers=_limit_headers(limit, remaining, seconds_to_reset),
            is_reusable=True,
        )
        await _fetch_all(client)  # learn the limits
        frozen.tick(2)  # the learning request leaves the one-second window

        assert await _count_passes(client) == expected_passes


@pytest.mark.asyncio
async def test_default_pace_is_used_without_limit_numbers(httpx2_mock: HTTPXMock):
    with freeze_time(real_asyncio=True):
        client = _client_with_fake_sleep(max_retries=1)
        httpx2_mock.add_response(url=EXAMPLE_URL, json=["a"], is_reusable=True)

        assert await _count_passes(client) == 3  # 216 per minute rounds down to 3/s


@pytest.mark.parametrize(
    "headers",
    [
        pytest.param({}, id="no-limit-headers"),
        pytest.param(
            {
                "x-ratelimit-limit": "abc",
                "x-ratelimit-remaining": "abc",
                "x-ratelimit-reset": "abc",
            },
            id="malformed-numbers",
        ),
        pytest.param({"x-ratelimit-limit": "5000"}, id="incomplete-numbers"),
        pytest.param(_limit_headers(0, 0, 3600), id="zero-limit-is-not-usable"),
        pytest.param(
            _limit_headers(30, 30, 3600, **{"x-ratelimit-resource": "search"}),
            id="other-bucket-is-ignored",
        ),
    ],
)
@pytest.mark.asyncio
async def test_pace_stays_fixed_without_usable_limit_numbers(
    httpx2_mock: HTTPXMock, headers: dict
):
    with freeze_time(real_asyncio=True):
        client = _client_with_fake_sleep(max_retries=1, rate_limit_per_minute=120)
        httpx2_mock.add_response(
            url=EXAMPLE_URL, json=["a"], headers=headers, is_reusable=True
        )

        assert await _count_passes(client) == 2  # 120 per minute is 2 per second


@pytest.mark.parametrize("hostname", [None, DEFAULT_HOSTNAME])
@pytest.mark.asyncio
async def test_pacing_works_on_github_dot_com_and_ghes(
    httpx2_mock: HTTPXMock, hostname: str | None
):
    with freeze_time(real_asyncio=True):
        client = _client_with_fake_sleep(max_retries=1, github_hostname=hostname)
        httpx2_mock.add_response(
            url=f"{client.base_url}/example?per_page=100",
            json=["a"],
            headers=_limit_headers(5000, 5000, 3600),
            is_reusable=True,
        )
        await _fetch_all(client)  # learn the limits

        assert await _count_passes(client) == 1  # 75 per minute rounds down to 1/s


@pytest.mark.asyncio
async def test_pace_numbers_update_between_pages(httpx2_mock: HTTPXMock):
    client = _client_with_fake_sleep(max_retries=1, per_page=2)
    page_one = f"{DEFAULT_BASE_URL}/example?per_page=2"
    page_two = f"{DEFAULT_BASE_URL}/example?per_page=2&page=2"
    page_three = f"{DEFAULT_BASE_URL}/example?per_page=2&page=3"
    # Page one advertises 7 requests per second. Page two lowers it to 1.
    httpx2_mock.add_response(
        url=page_one,
        json=["a", "b"],
        headers=_limit_headers(30000, 30000, 3600)
        | {"link": f'<{page_two}>; rel="next"'},
        is_reusable=False,
    )
    httpx2_mock.add_response(
        url=page_two,
        json=["c", "d"],
        headers=_limit_headers(5000, 5000, 3600)
        | {"link": f'<{page_three}>; rel="next"'},
        is_reusable=False,
    )
    httpx2_mock.add_response(url=page_three, json=["e", "f"], is_reusable=False)

    assert await _fetch_all(client) == ["a", "b", "c", "d", "e", "f"]
    # The last request followed page two's numbers. Page one's would give 7.
    assert client.rate_limit.amount == 1


@pytest.mark.asyncio
async def test_no_budget_left_waits_for_reset_before_sending(httpx2_mock: HTTPXMock):
    with freeze_time(real_asyncio=True) as frozen:
        client = _client_with_fake_sleep(max_retries=3)
        requests_sent_at_each_sleep: list[int] = []

        async def advance_clock(seconds: float) -> None:
            requests_sent_at_each_sleep.append(len(httpx2_mock.get_requests()))
            frozen.tick(seconds)

        client.retryer.sleep = AsyncMock(side_effect=advance_clock)
        httpx2_mock.add_response(
            url=EXAMPLE_URL,
            json=["a"],
            headers=_limit_headers(5000, 0, 600),
            is_reusable=False,
        )
        httpx2_mock.add_response(url=EXAMPLE_URL, json=["b"], is_reusable=False)

        first = await _fetch_all(client)
        second = await _fetch_all(client)

    assert (first, second) == (["a"], ["b"])
    (slept,) = _slept(client)
    assert 595 <= slept <= 632  # 10 minutes plus jitter of up to 30 seconds
    assert requests_sent_at_each_sleep == [1]  # nothing was sent while it waited


@pytest.mark.asyncio
async def test_server_rate_limit_error_says_what_the_server_sent(
    httpx2_mock: HTTPXMock,
):
    with freeze_time(real_asyncio=True):
        client = _client_with_fake_sleep(max_retries=1)
        httpx2_mock.add_response(
            url=EXAMPLE_URL,
            status_code=403,
            headers=_limit_headers(5000, 0, 600),
            json=RATE_LIMIT_MESSAGE,
        )

        with pytest.raises(RateLimitedError) as exc_info:
            await _fetch_all(client)

    assert str(exc_info.value).endswith(": server answered 403")
    assert exc_info.value.details == {
        "url": f"{DEFAULT_BASE_URL}/example",
        "reason": "server answered 403",
        "status_code": 403,
        "rate_limit_requests_per_hour": 5000,
        "rate_limit_requests_remaining": 0,
        "rate_limit_resets_in_seconds": 600,
    }


@pytest.mark.asyncio
async def test_blocked_before_sending_error_says_nothing_was_sent(
    httpx2_mock: HTTPXMock,
):
    # A whole-second clock keeps the reset time exact. The guard reads the clock
    # unrounded, and the header helper rounds down.
    with freeze_time("2026-10-13 12:00:00", real_asyncio=True):
        client = _client_with_fake_sleep(max_retries=1)
        httpx2_mock.add_response(
            url=EXAMPLE_URL, json=["a"], headers=_limit_headers(5000, 0, 600)
        )
        await _fetch_all(client)  # learn that the budget is used up

        with pytest.raises(RateLimitedError) as exc_info:
            await _fetch_all(client)

    assert str(exc_info.value).endswith(": not sent, remaining budget is 0")
    assert exc_info.value.details == {
        "url": f"{DEFAULT_BASE_URL}/example",
        "reason": "not sent, remaining budget is 0",
        "rate_limit_requests_per_hour": 5000,
        "rate_limit_requests_remaining": 0,
        "rate_limit_resets_in_seconds": 600,
    }
    assert len(httpx2_mock.get_requests()) == 1


@pytest.mark.asyncio
async def test_rate_limit_change_is_logged(
    httpx2_mock: HTTPXMock, caplog: pytest.LogCaptureFixture
):
    client = _client_with_fake_sleep(max_retries=1)
    httpx2_mock.add_response(
        url=EXAMPLE_URL,
        json=["a"],
        headers=_limit_headers(30000, 30000, 3600),
        is_reusable=True,
    )

    with caplog.at_level("INFO"):
        await _fetch_all(client)  # still the default pace of 3 per second
        await _fetch_all(client)  # now follows the advertised limit of 7 per second

    (change,) = [r for r in caplog.records if "rate limit changed" in r.getMessage()]
    assert "from 3 to 7 requests per second" in change.getMessage()
    fields = vars(change)
    assert fields["requests_per_second"] == 7
    assert fields["previous_requests_per_second"] == 3
    assert fields["pace_requests_per_minute"] == 450
    assert fields["rate_limit_requests_per_hour"] == 30000
    assert fields["rate_limit_requests_remaining"] == 30000
    assert fields["rate_limit_resets_in_seconds"] == pytest.approx(3600, abs=2)


@pytest.mark.asyncio
async def test_own_limiter_error_says_the_client_blocked_it(httpx2_mock: HTTPXMock):
    with freeze_time(real_asyncio=True):
        client = _client_with_fake_sleep(max_retries=1, rate_limit_per_minute=1)
        httpx2_mock.add_response(url=EXAMPLE_URL, json=["a"])
        await _fetch_all(client)

        with pytest.raises(RateLimitedError) as exc_info:
            await _fetch_all(client)

    assert str(exc_info.value).endswith(": client pace limit reached")
    assert exc_info.value.details == {
        "url": f"{DEFAULT_BASE_URL}/example",
        "reason": "client pace limit reached",
        "requests_per_second": 1,
    }


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

    with caplog.at_level("WARNING"):
        items = [item async for item in client.get_paginated("example")]

    assert items == ["a", "b", "c", "d"]

    # Test that the warning message was logged
    expected_warning = (
        "The GithubAPI has reached the maximum page size of 100. "
        "The returned data may be incomplete"
    )
    assert expected_warning in caplog.text


def test_constructor_keeps_its_optional_parameters():
    params = inspect.signature(GithubRestApiClient.__init__).parameters
    assert {k: v.default for k, v in params.items() if k != "self"} == {
        "auth_token": None,
        "github_hostname": None,
        "user_agent": None,
        "per_page": None,
        "max_retries": None,
        "rate_limit_per_minute": None,
        "max_retry_wait_seconds": None,
        "_kwargs": inspect.Parameter.empty,
    }


def test_rate_limit_is_the_window_in_use():
    item = _client_with_fake_sleep().rate_limit
    # The default pace of 216 per minute rounds down to 3 requests per second.
    assert (type(item), item.amount, item.multiples) == (RateLimitItemPerSecond, 3, 1)


def test_all_null_args():
    # noinspection PyTypeChecker
    assert GithubRestApiClient(auth_token=None, github_hostname=None)
