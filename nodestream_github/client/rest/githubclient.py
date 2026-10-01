"""githubclient

An async client for accessing GitHub.
"""

import json
import logging
from collections.abc import AsyncGenerator, Mapping
from enum import Enum
from typing import Any, NotRequired, TypedDict

import httpx
from limits import RateLimitItem, RateLimitItemPerMinute
from limits.aio.storage import MemoryStorage
from limits.aio.strategies import MovingWindowRateLimiter, RateLimiter
from tenacity import (
    AsyncRetrying,
    after_log,
    before_sleep_log,
    retry_if_exception_type,
    stop_after_attempt,
    wait_random_exponential,
)

import nodestream_github.types as types
from nodestream_github.logging import get_plugin_logger

DEFAULT_REQUEST_RATE_LIMIT_PER_MINUTE = int(13000 / 60)
DEFAULT_MAX_RETRIES = 20
DEFAULT_PAGE_SIZE = 100
DEFAULT_MAX_RETRY_WAIT_SECONDS = 300  # 5 minutes
DEFAULT_GITHUB_HOST = "api.github.com"


logger = get_plugin_logger(__name__)


class AllowedAuditActionsPhrases(Enum):
    BRANCH_PROTECTION = "protected_branch"


class RateLimitedError(Exception):
    def __init__(self, url: str | httpx.URL):
        super().__init__(f"Rate limited when calling {url}")


def _safe_get_json_error_message(response: httpx.Response) -> str:
    try:
        return response.json().get("message")
    except AttributeError:
        # ignore if no message
        return json.dumps(response.json())
    except ValueError:
        # ignore if no json
        return response.text


def log_fetch_problem(title: str, e: httpx.HTTPError):
    match e:
        case httpx.HTTPStatusError(response=response):
            error_message = _safe_get_json_error_message(response)
            logger.warning(
                "%s %s - %s%s",
                response.status_code,
                response.reason_phrase,
                e.request.url.path,
                f" - {error_message}" if error_message else "",
                stacklevel=2,
            )
        case _:
            logger.warning("Problem fetching %s", title, exc_info=e, stacklevel=2)


class GithubRestApiClientParams(TypedDict):
    auth_token: NotRequired[str | None]
    github_hostname: NotRequired[str | None]
    user_agent: NotRequired[str | None]
    per_page: NotRequired[int | None]
    max_retries: NotRequired[int | None]
    rate_limit_per_minute: NotRequired[int | None]
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
        self._default_headers = httpx.Headers({
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

        self._rate_limit = RateLimitItemPerMinute(
            (
                DEFAULT_REQUEST_RATE_LIMIT_PER_MINUTE
                if rate_limit_per_minute is None
                else rate_limit_per_minute
            ),
            1,
        )
        logger.info("GitHub REST RateLimit set to %s", self._rate_limit)
        self._rate_limiter = MovingWindowRateLimiter(self.limit_storage)
        self._session = httpx.AsyncClient()

        max_retry_wait_seconds = (
            DEFAULT_MAX_RETRY_WAIT_SECONDS
            if max_retry_wait_seconds is None
            else max_retry_wait_seconds
        )
        self._retryer = AsyncRetrying(
            wait=wait_random_exponential(max=max_retry_wait_seconds),
            stop=stop_after_attempt(self.max_retries),
            retry=retry_if_exception_type((RateLimitedError, httpx.TransportError)),
            before_sleep=before_sleep_log(logger, logging.WARNING),
            after=after_log(logger, logging.WARNING),
            reraise=True,
        )

    @property
    def retryer(self) -> AsyncRetrying:
        return self._retryer

    @property
    def session(self) -> httpx.AsyncClient:
        return self._session

    @property
    def rate_limiter(self) -> RateLimiter:
        return self._rate_limiter

    @property
    def rate_limit(self) -> RateLimitItem:
        return self._rate_limit

    @property
    def max_retries(self) -> int:
        return self._max_retries

    @property
    def limit_storage(self) -> MemoryStorage:
        return self._limit_storage

    @property
    def default_headers(self) -> httpx.Headers:
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
        params: types.QueryParamTypes | None,
        headers: types.HeaderTypes | None,
    ) -> httpx.Response:
        """
        Perform a GET request.

        DO NOT CALL THIS DIRECTLY. ONLY USE _get_retrying
        """
        can_try_hit: bool = await self.rate_limiter.test(self.rate_limit)
        if not can_try_hit:
            raise RateLimitedError(url)
        can_hit: bool = await self.rate_limiter.hit(self.rate_limit)
        if not can_hit:
            raise RateLimitedError(url)

        merged_headers = httpx.Headers(self.default_headers)
        merged_headers.update(headers)
        response = await self.session.get(
            url,
            params=params,
            headers=merged_headers,
        )
        response.raise_for_status()
        return response

    async def _get_retrying(
        self,
        url: str | httpx.URL,
        params: types.QueryParamTypes | None = None,
        headers: types.HeaderTypes | None = None,
    ) -> httpx.Response | None:
        return await self.retryer(self._get, url, params, headers)

    async def get_paginated(
        self,
        path: str,
        params: Mapping | None = None,
        headers: types.HeaderTypes | None = None,
    ) -> AsyncGenerator[dict[str, Any]]:
        url: str | None = f"{self.base_url}/{path}"
        query_params = {"per_page": self.per_page}
        if params:
            query_params.update(params)

        while url is not None:
            if "&page=100" in url:
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

            url = response.links.get("next", {}).get("url")

    async def get_item(
        self,
        path: str | httpx.URL,
        headers: types.HeaderTypes | None = None,
        params: types.QueryParamTypes | None = None,
    ) -> dict[str, Any]:
        url = f"{self.base_url}/{path}"
        response = await self._get_retrying(url, headers=headers, params=params)

        if response:
            return response.json()
        return {}
