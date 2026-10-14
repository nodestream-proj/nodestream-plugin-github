"""githubclient

An async client for accessing GitHub.
"""

import functools
import json
import logging
import time
import typing
from collections.abc import AsyncGenerator, Callable, Mapping
from enum import Enum
from typing import Any, NamedTuple, NotRequired, TypedDict

import httpx2
from httpx2 import URL, Headers, QueryParams
from limits import RateLimitItem, RateLimitItemPerSecond
from limits.aio.storage import MemoryStorage
from limits.aio.strategies import MovingWindowRateLimiter, RateLimiter
from tenacity import (
    AsyncRetrying,
    RetryCallState,
    after_log,
    before_sleep_log,
    retry_if_exception_type,
    stop_after_attempt,
    wait_random,
    wait_random_exponential,
)

from nodestream_github.logging import get_plugin_logger
from nodestream_github.types import HeaderTypes, QueryParamTypes

DEFAULT_REQUEST_RATE_LIMIT_PER_MINUTE = int(13000 / 60)
DEFAULT_MAX_RETRIES = 20
DEFAULT_PAGE_SIZE = 100
DEFAULT_MAX_RETRY_WAIT_SECONDS = 300  # 5 minutes
DEFAULT_GITHUB_HOST = "api.github.com"
RATE_LIMIT_FLOOR_SECONDS = 60  # GitHub advises waiting at least a minute
MAX_STATED_WAIT_SECONDS = 3900  # one hourly window plus margin
STATED_WAIT_JITTER_SECONDS = 30
PACE_FRACTION = 0.9  # stay at or under 90% of the limit the server advertises


logger = get_plugin_logger(__name__)


class AllowedAuditActionsPhrases(Enum):
    BRANCH_PROTECTION = "protected_branch"


class RateLimitedError(httpx2.HTTPError):
    """A request was blocked by the client's own limiter or by the server.

    `from_server` marks a limit the server reported. `wait_seconds` is the wait
    the server stated, when it stated one. `reason` says in a few words why the
    request was blocked. `details` holds the numbers behind it. The log lines pass
    `details` as `extra`, so a JSON log shows each key as a field.
    """

    def __init__(
        self,
        url: str | httpx2.URL,
        *,
        wait_seconds: float | None = None,
        from_server: bool = False,
        reason: str | None = None,
        details: Mapping[str, Any] | None = None,
    ):
        message = f"Rate limited when calling {url}"
        super().__init__(f"{message}: {reason}" if reason else message)
        self.wait_seconds = wait_seconds
        self.from_server = from_server
        self.details: dict[str, Any] = {"url": str(url)}
        if reason:
            self.details["reason"] = reason
        self.details.update(details or {})


def _safe_get_json_error_message(response: httpx2.Response) -> str:
    try:
        return response.json().get("message")
    except AttributeError:
        # ignore if no message
        return json.dumps(response.json())
    except ValueError:
        # ignore if no json
        return response.text


def _header_int(response: httpx2.Response, name: str) -> int | None:
    try:
        return int(response.headers[name])
    except (KeyError, ValueError):
        return None


def _is_rate_limit(response: httpx2.Response) -> bool:
    """Tell a rate-limit response from a permission failure."""
    if response.status_code == httpx2.codes.TOO_MANY_REQUESTS:
        return True
    if response.status_code != httpx2.codes.FORBIDDEN:
        return False
    if "retry-after" in response.headers:
        return True
    if _header_int(response, "x-ratelimit-remaining") == 0:
        return True
    message = str(_safe_get_json_error_message(response) or "")
    return "rate limit" in message.lower()


def _bounded_wait(seconds: float | None) -> float | None:
    """Drop a stated wait that is missing or too long to be believed."""
    if seconds is None or seconds > MAX_STATED_WAIT_SECONDS:
        return None
    return max(seconds, 0)


def _stated_wait_seconds(response: httpx2.Response) -> float | None:
    """The wait the server states, or None when it states none we can use."""
    wait = _header_int(response, "retry-after")
    if wait is None and _header_int(response, "x-ratelimit-remaining") == 0:
        reset = _header_int(response, "x-ratelimit-reset")
        if reset is not None:
            wait = reset - int(time.time())
    return _bounded_wait(wait)


def _server_limit_fields(response: httpx2.Response) -> dict[str, Any]:
    """Collect the numbers in a server rate-limit response for the log.

    GitHub states the limit as requests per hour.
    """
    reset = _header_int(response, "x-ratelimit-reset")
    resets_in = None if reset is None else reset - int(time.time())
    fields = {
        "status_code": response.status_code,
        "rate_limit_requests_per_hour": _header_int(response, "x-ratelimit-limit"),
        "rate_limit_requests_remaining": _header_int(response, "x-ratelimit-remaining"),
        "rate_limit_resets_in_seconds": resets_in,
        "retry_after_seconds": _header_int(response, "retry-after"),
        "rate_limit_resource": response.headers.get("x-ratelimit-resource"),
    }
    return {key: value for key, value in fields.items() if value is not None}


class _RateLimitState(NamedTuple):
    limit: int
    remaining: int
    reset: int


def _read_rate_limit_state(response: httpx2.Response) -> _RateLimitState | None:
    """Read the server's limit numbers. Skip other buckets and unusable values."""
    if response.headers.get("x-ratelimit-resource", "core") != "core":
        return None
    limit = _header_int(response, "x-ratelimit-limit")
    remaining = _header_int(response, "x-ratelimit-remaining")
    reset = _header_int(response, "x-ratelimit-reset")
    if limit is None or limit <= 0 or remaining is None or reset is None:
        return None
    return _RateLimitState(limit, remaining, reset)


def _pace_per_minute(
    user_cap: int | None, state: _RateLimitState | None, now: float
) -> float:
    """Return the pace in requests per minute.

    The ceiling is 90% of the rate the server advertises. A cap the user set stays
    an upper bound. The pace slows below the ceiling when the remaining budget
    would run out before the reset. A stale reset time leaves the pace at the
    ceiling. Without limit numbers, the pace is the user cap or the default.
    """
    if user_cap is not None and user_cap <= 0:
        return 0.0
    if state is None:
        return DEFAULT_REQUEST_RATE_LIMIT_PER_MINUTE if user_cap is None else user_cap
    ceiling = max(int(PACE_FRACTION * state.limit / 60), 1)
    cap = ceiling if user_cap is None else min(user_cap, ceiling)
    pace = cap
    if state.reset > now:
        minutes_left = max((state.reset - now) / 60, 1)
        pace = min(cap, PACE_FRACTION * state.remaining / minutes_left)
    return max(pace, 1)


def _requests_per_second(pace_per_minute: float) -> int:
    """Return the whole requests per second that meter a pace.

    A one-second window holds whole requests. The count rounds down, so it never
    exceeds the pace. It is never below one, because a window must hold a request.
    A pace of zero admits none.
    """
    if pace_per_minute <= 0:
        return 0
    return max(int(pace_per_minute / 60), 1)


def _state_fields(state: _RateLimitState | None, now: float) -> dict[str, int]:
    """Collect the server's limit numbers for the log.

    GitHub states the limit as requests per hour.
    """
    if state is None:
        return {}
    return {
        "rate_limit_requests_per_hour": state.limit,
        "rate_limit_requests_remaining": state.remaining,
        "rate_limit_resets_in_seconds": max(round(state.reset - now), 0),
    }


def _wait_for_rate_limit(
    max_retry_wait_seconds: float,
) -> Callable[[RetryCallState], float]:
    """Wait the stated time plus jitter, else back off. Floor server limits."""
    backoff = wait_random_exponential(max=max_retry_wait_seconds)
    jitter = wait_random(0, STATED_WAIT_JITTER_SECONDS)

    def wait(retry_state: RetryCallState) -> float:
        error = retry_state.outcome.exception() if retry_state.outcome else None
        if not isinstance(error, RateLimitedError) or not error.from_server:
            return backoff(retry_state)
        if error.wait_seconds is not None:
            return error.wait_seconds + jitter(retry_state)
        return max(backoff(retry_state), RATE_LIMIT_FLOOR_SECONDS)

    return wait


def _retry_log_level(retry_state: RetryCallState) -> int:
    """Warn about retries the server caused. Log the client's own pacing at debug."""
    error = retry_state.outcome.exception() if retry_state.outcome else None
    own_limiter = isinstance(error, RateLimitedError) and not error.from_server
    return logging.DEBUG if own_limiter else logging.WARNING


def _log_before_sleep(retry_state: RetryCallState) -> None:
    error = retry_state.outcome.exception() if retry_state.outcome else None
    if not isinstance(error, RateLimitedError) or retry_state.next_action is None:
        before_sleep_log(logger, _retry_log_level(retry_state))(retry_state)
        return
    wait = retry_state.next_action.sleep
    logger.log(
        _retry_log_level(retry_state),
        "Retrying in %.0f seconds as it raised RateLimitedError: %s.",
        wait,
        error,
        extra={
            **error.details,
            "attempt": retry_state.attempt_number,
            "wait_seconds": round(wait),
        },
    )


def _log_after_attempt(retry_state: RetryCallState) -> None:
    after_log(logger, _retry_log_level(retry_state))(retry_state)


def log_fetch_problem(title: str, e: httpx2.HTTPError):
    match e:
        case httpx2.HTTPStatusError(response=response):
            error_message = _safe_get_json_error_message(response)
            logger.warning(
                "%s %s - %s%s",
                response.status_code,
                response.reason_phrase,
                e.request.url.path,
                f" - {error_message}" if error_message else "",
                stacklevel=2,
            )
        case RateLimitedError():
            logger.warning(
                "Gave up fetching %s: %s", title, e, stacklevel=2, extra=e.details
            )
        case _:
            logger.warning("Problem fetching %s", title, exc_info=e, stacklevel=2)


@functools.lru_cache
def _required_keys(typed_dict: type) -> frozenset[str]:
    hints = typing.get_type_hints(typed_dict, include_extras=True)
    return frozenset(
        key for key, hint in hints.items() if typing.get_origin(hint) is not NotRequired
    )


def has_required_keys(title: str, record: Mapping[str, Any], typed_dict: type) -> bool:
    missing = [key for key in _required_keys(typed_dict) if key not in record]
    if missing:
        logger.warning(
            "Skipping malformed %s, missing keys %s: %s",
            title,
            missing,
            record,
            stacklevel=2,
        )
    return not missing


class GithubRestApiClientParams(TypedDict):
    auth_token: NotRequired[str | None]
    github_hostname: NotRequired[str | None]
    user_agent: NotRequired[str | None]
    per_page: NotRequired[int | None]
    max_retries: NotRequired[int | None]
    # Upper bound on the pace, in requests per minute. The client meters whole
    # requests per second. It rounds down and never goes below 1 per second.
    # For example, 225 allows 3 per second, which is 180 per minute.
    rate_limit_per_minute: NotRequired[int | None]
    # Caps the exponential backoff only. A server rate limit waits the stated time
    # plus jitter, up to MAX_STATED_WAIT_SECONDS. With no stated time, it waits at
    # least RATE_LIMIT_FLOOR_SECONDS, even when this value is lower.
    max_retry_wait_seconds: NotRequired[int | None]


class GithubRestApiClient:
    def __init__(
        self,
        *,
        auth_token: str | None = None,
        github_hostname: str | None = None,
        user_agent: str | None = None,
        per_page: int | None = None,
        max_retries: int | None = None,
        rate_limit_per_minute: int | None = None,
        max_retry_wait_seconds: int | None = None,
        **_kwargs: Any,
    ):
        if per_page is None:
            per_page = DEFAULT_PAGE_SIZE
        elif per_page < 1:
            msg = "page_size must be an integer greater than 0"
            raise ValueError(msg)

        if max_retries is None:
            max_retries = DEFAULT_MAX_RETRIES
        elif max_retries < 0:
            msg = "max_retries must be a positive integer"
            raise ValueError(msg)

        self._auth_token = auth_token
        if github_hostname == "api.github.com" or github_hostname is None:
            self._base_url = "https://api.github.com"
            self._is_default_hostname = True
        else:
            self._base_url = f"https://{github_hostname}/api/v3"
            self._is_default_hostname = False

        self._per_page = per_page
        self._limit_storage = MemoryStorage()
        self._default_headers = Headers({
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        })
        if not self.auth_token:
            logger.warning("Missing auth_token.")
        else:
            self._default_headers.update({"Authorization": f"Bearer {self.auth_token}"})

        if user_agent:
            self._default_headers["User-Agent"] = user_agent
        self._max_retries = max_retries

        self._user_cap = rate_limit_per_minute
        self._rate_limit_state: _RateLimitState | None = None
        pace = _pace_per_minute(self._user_cap, None, 0)
        self._rate_limit = RateLimitItemPerSecond(_requests_per_second(pace))
        logger.info(
            "GitHub REST rate limit set to %s requests per second. "
            "Pace is %.0f requests per minute.",
            self._rate_limit.amount,
            pace,
        )
        self._rate_limiter = MovingWindowRateLimiter(self.limit_storage)
        self._session = httpx2.AsyncClient()

        max_retry_wait_seconds = (
            DEFAULT_MAX_RETRY_WAIT_SECONDS
            if max_retry_wait_seconds is None
            else max_retry_wait_seconds
        )
        self._retryer = AsyncRetrying(
            wait=_wait_for_rate_limit(max_retry_wait_seconds),
            stop=stop_after_attempt(self.max_retries),
            retry=retry_if_exception_type((RateLimitedError, httpx2.TransportError)),
            before_sleep=_log_before_sleep,
            after=_log_after_attempt,
            reraise=True,
        )

    @property
    def retryer(self) -> AsyncRetrying:
        return self._retryer

    @property
    def session(self) -> httpx2.AsyncClient:
        return self._session

    @property
    def rate_limiter(self) -> RateLimiter:
        return self._rate_limiter

    @property
    def rate_limit(self) -> RateLimitItem:
        """The limit item in use. Its window follows the current pace."""
        return self._rate_limit

    @property
    def max_retries(self) -> int:
        return self._max_retries

    @property
    def limit_storage(self) -> MemoryStorage:
        return self._limit_storage

    @property
    def default_headers(self) -> HeaderTypes:
        return self._default_headers

    @property
    def auth_token(self) -> str | None:
        return self._auth_token

    @property
    def base_url(self) -> str:
        return self._base_url

    @property
    def per_page(self) -> int:
        return self._per_page

    @property
    def is_default_hostname(self) -> bool:
        return self._is_default_hostname

    async def _get(
        self,
        url: str,
        params: QueryParamTypes,
        headers: HeaderTypes,
    ) -> httpx2.Response:
        """
        Perform a GET request.

        DO NOT CALL THIS DIRECTLY. ONLY USE _get_retrying
        """
        now = time.time()
        state = self._rate_limit_state
        if state is not None and state.remaining == 0 and state.reset > now:
            raise RateLimitedError(
                url,
                wait_seconds=_bounded_wait(state.reset - now),
                from_server=True,
                reason="not sent, remaining budget is 0",
                details=_state_fields(state, now),
            )
        pace = _pace_per_minute(self._user_cap, state, now)
        rate_limit = RateLimitItemPerSecond(_requests_per_second(pace))
        if rate_limit.amount != self._rate_limit.amount:
            logger.info(
                "GitHub REST rate limit changed from %s to %s requests per second. "
                "Pace is %.0f requests per minute.",
                self._rate_limit.amount,
                rate_limit.amount,
                pace,
                extra={
                    "requests_per_second": rate_limit.amount,
                    "previous_requests_per_second": self._rate_limit.amount,
                    "pace_requests_per_minute": round(pace),
                    **_state_fields(state, now),
                },
            )
        self._rate_limit = rate_limit
        pace_details = {"requests_per_second": self.rate_limit.amount}
        can_try_hit: bool = await self.rate_limiter.test(self.rate_limit)
        if not can_try_hit:
            raise RateLimitedError(
                url, reason="client pace limit reached", details=pace_details
            )
        can_hit: bool = await self.rate_limiter.hit(self.rate_limit)
        if not can_hit:
            raise RateLimitedError(
                url, reason="client pace limit reached", details=pace_details
            )

        merged_headers = Headers(self.default_headers)
        merged_headers.update(headers)
        response = await self.session.get(
            url,
            params=params,
            headers=merged_headers,
        )
        if (new_state := _read_rate_limit_state(response)) is not None:
            self._rate_limit_state = new_state
        try:
            response.raise_for_status()
        except httpx2.HTTPStatusError as e:
            if _is_rate_limit(response):
                raise RateLimitedError(
                    url,
                    wait_seconds=_stated_wait_seconds(response),
                    from_server=True,
                    reason=f"server answered {response.status_code}",
                    details=_server_limit_fields(response),
                ) from e
            raise
        return response

    async def _get_retrying(
        self,
        url: str | httpx2.URL,
        params: QueryParamTypes | None = None,
        headers: HeaderTypes | None = None,
    ) -> httpx2.Response | None:
        return await self.retryer(self._get, url, params, headers)

    async def get_paginated(
        self,
        path: str,
        params: QueryParamTypes | None = None,
        headers: HeaderTypes | None = None,
    ) -> AsyncGenerator[dict[str, Any]]:
        url: str = f"{self.base_url}/{path}"
        _url = URL(url)
        query_params = {"per_page": self.per_page}

        if params and isinstance(params, Mapping):
            query_params = {**query_params, **params}
        elif params and isinstance(params, QueryParams):
            query_params.update(*params.items())
        elif params:
            query_params.update(*params)

        while _url is not None:
            query_params.update(_url.params)
            if query_params.get("page") == "100":
                logger.warning(
                    "The GithubAPI has reached the maximum page size "
                    "of 100. The returned data may be incomplete for request: %s",
                    url,
                )

            response = await self._get_retrying(
                url, headers=headers, params=query_params
            )
            if not response:
                return
            for tag in response.json():
                yield tag

            next_url = response.links.get("next", {}).get("url")
            _url = URL(next_url) if next_url else None

    async def get_item(
        self,
        path: str | httpx2.URL,
        headers: HeaderTypes | None = None,
        params: QueryParamTypes | None = None,
    ) -> dict[str, Any]:
        url = f"{self.base_url}/{path}"
        response = await self._get_retrying(url, headers=headers, params=params)

        if response:
            return response.json()
        return {}
