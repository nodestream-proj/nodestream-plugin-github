import httpx
import pytest
from freezegun import freeze_time
from pytest_httpx import HTTPXMock

from nodestream_github.client.githubclient import (
    GithubRestApiClient,
    RateLimitedError,
    generate_date_range,
    validate_lookback_period,
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


# Test generate_date_range


def test_generate_date_range_empty_lookback_period():
    result = generate_date_range({})
    assert result == []


@freeze_time("2025-08-01")
def test_generate_date_range_days_only():
    result = generate_date_range({"days": 3})
    expected = ["2025-07-29", "2025-07-30", "2025-07-31", "2025-08-01"]
    assert result == expected


@freeze_time("2025-08-01")
def test_generate_date_range_zero_days():
    """Test with zero days (same day only)."""
    result = generate_date_range({"days": 0})
    expected = ["2025-08-01"]
    assert result == expected


@freeze_time("2025-08-01")
def test_generate_date_range_months_only():
    result = generate_date_range({"months": 1})
    # July 1 to August 1 = 32 days
    assert len(result) == 32
    assert result[0] == "2025-07-01"
    assert result[-1] == "2025-08-01"


@freeze_time("2025-08-01")
def test_generate_date_range_years_only():
    result = generate_date_range({"years": 1})
    assert len(result) == 366
    assert result[0] == "2024-08-01"
    assert result[-1] == "2025-08-01"


@freeze_time("2025-08-01")
def test_generate_date_range_combined_periods():
    """Test with combined periods."""
    result = generate_date_range({"months": 1, "days": 5})
    assert result[0] == "2025-06-26"
    assert result[-1] == "2025-08-01"


@freeze_time("2025-08-01")
def test_generate_date_range_complex_combination():
    """Test with years, months, and days."""
    result = generate_date_range({"years": 1, "months": 2, "days": 10})
    assert result[0] == "2024-05-22"
    assert result[-1] == "2025-08-01"


# Test validate_lookback_period


def test_validate_lookback_period_valid_input():
    result = validate_lookback_period({"days": 7, "months": 2, "years": 1})
    expected = {"days": 7, "months": 2, "years": 1}
    assert result == expected


def test_validate_lookback_period_empty_dict():
    result = validate_lookback_period({})
    assert result == {}


def test_validate_lookback_period_single_value():
    result = validate_lookback_period({"days": 30})
    assert result == {"days": 30}


def test_validate_lookback_period_string_to_int_conversion():
    result = validate_lookback_period({"days": "7", "months": "2"})
    expected = {"days": 7, "months": 2}
    assert result == expected


def test_validate_lookback_period_zero_value():
    with pytest.raises(ValueError, match="Formatting lookback period failed"):
        validate_lookback_period({"days": 0})


def test_validate_lookback_period_negative_value():
    with pytest.raises(ValueError, match="Formatting lookback period failed"):
        validate_lookback_period({"days": -5})


def test_validate_lookback_period_multiple_negative_values():
    with pytest.raises(ValueError, match="Formatting lookback period failed"):
        validate_lookback_period({"days": 7, "months": -1, "years": 2})


def test_validate_lookback_period_zero_string():
    with pytest.raises(ValueError, match="Formatting lookback period failed"):
        validate_lookback_period({"days": "0"})


def test_validate_lookback_period_negative_string():
    with pytest.raises(ValueError, match="Formatting lookback period failed"):
        validate_lookback_period({"months": "-10"})


def test_validate_lookback_period_invalid_string():
    with pytest.raises(ValueError, match="Formatting lookback period failed"):
        validate_lookback_period({"days": "invalid"})


def test_validate_lookback_period_invalid_type():
    with pytest.raises(ValueError, match="Formatting lookback period failed"):
        validate_lookback_period({"days": []})


def test_validate_lookback_period_none_value():
    with pytest.raises(ValueError, match="Formatting lookback period failed"):
        validate_lookback_period({"days": None})
