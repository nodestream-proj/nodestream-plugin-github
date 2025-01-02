"""githubclient

An async client for accessing GitHub.
"""

import datetime
import logging
import os
from enum import Enum

from httpx import AsyncClient, HTTPStatusError, Request, TransportError
from limits import RateLimitItemPerMinute
from limits.aio.storage import MemoryStorage
from limits.aio.strategies import MovingWindowRateLimiter
from tenacity import (
    after_log,
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_random_exponential,
)

# per hour / 60 / 60
DEFAULT_REQUEST_RATE_LIMIT = int(13000 / 60)

logger = logging.getLogger(__name__)


class AllowedAuditActionsPhrases(Enum):
    BRANCH_PROTECTION = "protected_branch"


class RateLimitedException(Exception):
    def __init__(self, url):
        super().__init__(f"Rate limited when calling {url}")


class GithubRestApiClient:
    def __init__(self, auth_token, github_endpoint, **kwargs):
        self.auth_token = auth_token
        self.github_endpoint = github_endpoint
        if "page_size" in kwargs:
            self.page_size = kwargs["page_size"]
        else:
            self.page_size = 100
        logger.debug("Page Size: %s", self.page_size)
        self.limit_storage = MemoryStorage()
        if "user_agent" in kwargs:
            user_agent = kwargs["user_agent"]
        else:
            user_agent = " ".join(
                [
                    os.environ.get("APP_NAME", "etwcrons_app_unknown"),
                    os.environ.get("SELECTED_PIPELINE", "pipeline_unknown"),
                ]
            )
        logger.debug("User Agent: %s", user_agent)
        self.headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": "Bearer " + self.auth_token,
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": user_agent,
        }
        rate_limit = kwargs.get("request_rate_limit")
        if not rate_limit:
            rate_limit = DEFAULT_REQUEST_RATE_LIMIT
        logger.warning("RateLimit per minute: %s", rate_limit)
        self.limit_per_second = RateLimitItemPerMinute(rate_limit, 1)
        self.rate_limiter = MovingWindowRateLimiter(self.limit_storage)
        self.session = AsyncClient()

    async def log_metrics(self, method: str):
        waiting = await self.rate_limiter.get_window_stats(self.limit_per_second)
        logger.info(f"{method=}, {waiting=}")

    @retry(
        wait=wait_random_exponential(),
        stop=stop_after_attempt(30),
        retry=retry_if_exception_type((RateLimitedException, TransportError)),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        after=after_log(logger, logging.ERROR),
    )
    async def _get(self, url):
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
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return response

    async def _generate_and_paginate(self, url, params=None):
        page_params = {"per_page": self.page_size}
        if params:
            page_params.update(params)
        req = Request("GET", url, params=page_params)
        url = req.url
        while url is not None:
            response = await self._get(url)
            if response is None:
                return
            for tag in response.json():
                yield tag
            url = response.links.get("next")
            if url is not None:
                url = url["url"]

    def get_repos_from_page(self, for_page=1):
        url = f"{self.github_endpoint}/user/repos?per_page={self.page_size}&page={for_page}"
        return self._get(url)

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

    async def get(self, path, params=None):
        url = f"{self.github_endpoint}/{path}"
        logger.debug("GET (paginated): %s", url)
        async for page in self._generate_and_paginate(url, params=params):
            yield page

    async def get_item(self, path):
        url = f"{self.github_endpoint}/{path}"
        logger.debug("GET: %s", url)
        response = await self._get(url)
        return response.json()

    async def get_repos(self):
        url = f"{self.github_endpoint}/user/repos"
        async for page in self._generate_and_paginate(url):
            yield page

    async def get_repo_branches(self, repo_with_owner):
        url = f"{self.github_endpoint}/repos/{repo_with_owner}/branches"
        async for page in self._generate_and_paginate(url):
            yield page

    async def get_repo_collaborators(self, repo_with_owner):
        url = f"{self.github_endpoint}/repos/{repo_with_owner}/collaborators"
        async for page in self._generate_and_paginate(url):
            yield page

    async def get_repo_releases(self, repo_with_owner):
        url = f"{self.github_endpoint}/repos/{repo_with_owner}/releases"
        async for page in self._generate_and_paginate(url):
            yield page

    async def get_repo_tags(self, repo_with_owner):
        url = f"{self.github_endpoint}/repos/{repo_with_owner}/tags"
        async for page in self._generate_and_paginate(url):
            yield page

    async def get_user(self, username):
        url = f"{self.github_endpoint}/users/{username}"
        response = await self._get(url)
        return response.json()

    async def get_users(self):
        url = f"{self.github_endpoint}/users"
        async for page in self._generate_and_paginate(url):
            yield page
        await self.log_metrics("get_users")

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
