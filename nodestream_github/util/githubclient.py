"""githubclient

An async client for accessing GitHub.
"""

import datetime
import logging
import types
from enum import Enum
from typing import AsyncIterator

from httpx import AsyncClient, HTTPStatusError, Request, TransportError
from limits import RateLimitItemPerMinute
from limits.aio.storage import MemoryStorage
from limits.aio.strategies import MovingWindowRateLimiter
from tenacity import (
    AsyncRetrying,
    after_log,
    before_sleep_log,
    retry_if_exception_type,
    stop_after_attempt,
    wait_random_exponential,
)

from nodestream_github.types import JSONType

from .logutil import init_logger

# per hour / 60 / 60
DEFAULT_REQUEST_RATE_LIMIT = int(13000 / 60)
DEFAULT_MAX_RETRIES = 20
DEFAULT_PAGE_SIZE = 100


logger = init_logger(__name__)


class AllowedAuditActionsPhrases(Enum):
    BRANCH_PROTECTION = "protected_branch"


class RateLimitedException(Exception):
    def __init__(self, url):
        super().__init__(f"Rate limited when calling {url}")


class GithubRestApiClient:
    def __init__(self, auth_token, github_endpoint, user_agent, **kwargs):
        logger.debug("client kwargs: %s", kwargs)
        self.auth_token = auth_token
        self.github_endpoint = github_endpoint
        if "page_size" in kwargs:
            self.page_size = kwargs["page_size"]
        else:
            self.page_size = DEFAULT_PAGE_SIZE
        logger.debug("Page Size: %s", self.page_size)
        self.limit_storage = MemoryStorage()
        if not user_agent:
            raise ValueError("user_agent")
        logger.debug("User Agent: %s", user_agent)
        self.headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": "Bearer " + self.auth_token,
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": user_agent,
        }
        self.max_retries = kwargs.get("max_retries", -1)
        if self.max_retries < 0:
            self.max_retries = DEFAULT_MAX_RETRIES
        logger.debug("Max retries: %s", self.max_retries)

        rate_limit = kwargs.get("request_rate_limit", -1)
        if rate_limit < 0:
            rate_limit = DEFAULT_REQUEST_RATE_LIMIT
        logger.debug("RateLimit per minute: %s", rate_limit)
        self.limit_per_second = RateLimitItemPerMinute(rate_limit, 1)
        self.rate_limiter = MovingWindowRateLimiter(self.limit_storage)
        self.session = AsyncClient()

    async def log_metrics(self, method: str):
        waiting = await self.rate_limiter.get_window_stats(self.limit_per_second)
        logger.info(f"{method=}, {waiting=}")

    @property
    def retryer(self):
        return AsyncRetrying(
            wait=wait_random_exponential(),
            stop=stop_after_attempt(self.max_retries),
            retry=retry_if_exception_type((RateLimitedException, TransportError)),
            before_sleep=before_sleep_log(logger, logging.WARNING),
            after=after_log(logger, logging.WARNING),
            reraise=True,
        )

    async def _get(self, url):
        return await self.retryer(self._get_inside_retry, url)

    async def _get_inside_retry(self, url):
        can_try_hit: bool = await self.rate_limiter.test(self.limit_per_second)
        if not can_try_hit:
            raise RateLimitedException(url)
        can_hit: bool = await self.rate_limiter.hit(self.limit_per_second)
        if not can_hit:
            raise RateLimitedException(url)

        response = await self.session.get(
            url,
            headers=self.headers,
        )
        response.raise_for_status()
        return response

    async def _generate_and_paginate(
        self, url, params=None
    ) -> types.AsyncGeneratorType[any]:
        page_params = {"per_page": self.page_size}
        if params:
            page_params.update(params)
        req = Request("GET", url, params=page_params)
        url = req.url
        while url is not None:
            logger.debug(f"{url=}")
            response = await self._get(url)
            if response is None:
                return
            for tag in response.json():
                yield tag

            url = response.links.get("next", {}).get("url")

    async def get_audit_logs(
        self,
        org_repo,
        start_date: datetime = datetime.datetime.now(datetime.UTC)
        - datetime.timedelta(weeks=4),
        end_date: datetime = datetime.datetime.now(datetime.UTC),
        action: (
            AllowedAuditActionsPhrases | str
        ) = AllowedAuditActionsPhrases.BRANCH_PROTECTION,
    ):
        """Returns all the audit logs for the requested repository for the specified action.
        Will default to audit logs that go back to start_date and up to end_end.

        Args:
            org_repo (_type_): "GitHub identifier of a repository in the format `orgname/reponame`"
            start_date (datetime, optional): _description_. Defaults to datetime.datetime.now(datetime.UTC)-datetime.timedelta(weeks=4).
            end_date (datetime, optional): _description_. Defaults to datetime.datetime.now(datetime.UTC).
            action (Union[ AllowedAuditActionsPhrases, str ], optional): _description_. Defaults to AllowedAuditActionsPhrases.BRANCH_PROTECTION.

        Yields:
            dict: All relevant audit logs
        """
        # action can be provided as the string value as well.
        org_name = org_repo.split("/")[0]
        action = AllowedAuditActionsPhrases(action)
        # using the TZ +00:00 breaks the Api as it uses the '+' sign to build the query. After setting to UTC datetime I am removing TZ info from the object now.
        url = f"{self.github_endpoint}/orgs/{org_name}/audit-log?order=asc&phrase=repo:{org_repo}+action:{action.value}+created:{start_date.isoformat().replace('+00:00', 'Z')}..{end_date.isoformat().replace('+00:00', 'Z')}"
        async for page in self._generate_and_paginate(url):
            yield page

    async def get(self, path: str, params=None) -> AsyncIterator[JSONType]:
        url = f"{self.github_endpoint}/{path}"
        logger.debug("GET (paginated): %s", url)
        async for page in self._generate_and_paginate(url, params=params):
            yield page

    async def get_item(self, path):
        url = f"{self.github_endpoint}/{path}"
        logger.debug("GET: %s", url)
        response = await self._get(url)

        if response:
            return response.json()
        else:
            return {}

    # API Call to get branch protection settings for a given org+repo+branch
    async def get_repo_branch_protection(self, repo_with_owner, branch):
        url = f"{self.github_endpoint}/repos/{repo_with_owner}/branches/{branch}/protection"
        try:
            response = await self.session.get(
                url,
                headers=self.headers,
            )
            response.raise_for_status()
            return response.json()
        except HTTPStatusError as err:
            if err.response.status_code == 404:
                logger.info(
                    "Branch protection is not enabled for Github repo: %s. branch: %s",
                    repo_with_owner,
                    branch,
                )
            else:
                logger.error(
                    "HttpError while retrieving branch protection settings: %s. branch: %s",
                    err,
                    branch,
                )
            return None
