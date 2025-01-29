"""githubclient

An async client for accessing GitHub.
"""

import json
import logging
from collections.abc import AsyncGenerator
from enum import Enum

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


def _fetch_problem(title: str, e: httpx.HTTPError):
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
        else:
            self._base_url = f"https://{github_hostname}/api/v3"

        self._per_page = per_page
        self._limit_storage = MemoryStorage()
        if not self.auth_token:
            logger.warning("Missing auth_token.")
        self._default_headers = httpx.Headers({
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {self.auth_token}",
            "X-GitHub-Api-Version": "2022-11-28",
        })
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
            wait=wait_random_exponential(
                max=max_retry_wait_seconds,
            ),
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
    def auth_token(self) -> str:
        return self._auth_token

    @property
    def base_url(self) -> str:
        return self._base_url

    @property
    def per_page(self) -> int:
        return self._per_page

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
    ) -> httpx.Response:
        return await self.retryer(self._get, url, params, headers)

    async def _get_paginated(
        self,
        path: str,
        params: types.QueryParamTypes | None = None,
        headers: types.HeaderTypes | None = None,
    ) -> AsyncGenerator[types.JSONType]:
        url = f"{self.base_url}/{path}"
        query_params = {"per_page": self.per_page}
        if params:
            query_params.update(params)

        while url is not None:
            response = await self._get_retrying(
                url, headers=headers, params=query_params
            )
            if response is None:
                return
            for tag in response.json():
                yield tag

            url = response.links.get("next", {}).get("url")

    async def _get_item(
        self,
        path: str | httpx.URL,
        headers: types.HeaderTypes | None = None,
        params: types.QueryParamTypes | None = None,
    ) -> types.JSONType:
        url = f"{self.base_url}/{path}"
        response = await self._get_retrying(url, headers=headers, params=params)

        if response:
            return response.json()
        return {}

    async def fetch_repos_for_org(
        self, org_login: str, repo_type: str | None = None
    ) -> AsyncGenerator[types.GithubRepo]:
        """Fetches repositories for the specified organization.

        Note: In order to see the security_and_analysis block for a repository you
        must have admin permissions for the repository or be an owner or security
        manager for the organization that owns the repository.

        https://docs.github.com/en/enterprise-server@3.12/rest/repos/repos?apiVersion=2022-11-28#list-organization-repositories

        If using a fine-grained access token, the token must have the "Metadata"
        repository permissions (read)
        """
        try:
            params = {}
            if repo_type:
                params["type"] = repo_type
            async for response in self._get_paginated(
                f"orgs/{org_login}/repos", params=params
            ):
                yield response

        except httpx.HTTPError as e:
            _fetch_problem(f"repos for org {org_login}", e)

    async def fetch_members_for_org(
        self, org_login: str, role: str | None = None
    ) -> AsyncGenerator[types.GithubUser]:
        """Fetch all users who are members of an organization.

        If the authenticated user is also a member of this organization then both
        concealed and public members will be returned.

        https://docs.github.com/en/enterprise-server@3.12/rest/orgs/members?apiVersion=2022-11-28#list-organization-members

        Fine-grained access tokens require the "Members" organization permissions (read)
        """
        try:
            params = {}
            if role:
                params["role"] = role
            async for member in self._get_paginated(
                f"orgs/{org_login}/members", params=params
            ):
                yield member

        except httpx.HTTPError as e:
            _fetch_problem(f"members for org {org_login}", e)

    async def fetch_all_organizations(self) -> AsyncGenerator[types.GithubOrg]:
        """Fetches all organizations, in the order that they were created.

        https://docs.github.com/en/enterprise-server@3.12/rest/orgs/orgs?apiVersion=2022-11-28#list-organizations
        """
        try:
            async for org in self._get_paginated("organizations"):
                yield org
        except httpx.HTTPError as e:
            _fetch_problem("all organizations", e)

    async def fetch_full_org(self, org_login: str) -> types.GithubOrg | None:
        """Fetches the complete org record.

        https://docs.github.com/en/enterprise-server@3.12/rest/orgs/orgs?apiVersion=2022-11-28#get-an-organization

        Personal access tokens (classic) need the admin:org scope to see the
        full details about an organization.

        The fine-grained token does not require any permissions.
        """
        try:
            logger.debug("fetching full org=%s", org_login)
            return await self._get_item(f"orgs/{org_login}")
        except httpx.HTTPError as e:
            _fetch_problem(f"full organization info for {org_login}", e)

    async def fetch_repos_for_user(
        self,
        user_login: str,
        repo_type: str | None = None,
    ) -> AsyncGenerator[types.GithubRepo]:
        """Fetches repositories for a user.

        https://docs.github.com/en/enterprise-server@3.12/rest/repos/repos?apiVersion=2022-11-28#list-repositories-for-a-user

        Fine-grained token must have the "Metadata" repository permissions (read)
        """
        try:
            params = {}
            if repo_type:
                params["type"] = repo_type
            async for repo in self._get_paginated(
                f"users/{user_login}/repos", params=params
            ):
                yield repo

        except httpx.HTTPError as e:
            _fetch_problem(f"repos for user {user_login}", e)

    async def fetch_languages_for_repo(
        self, owner_login: str, repo_name: str
    ) -> AsyncGenerator[str]:
        """Fetch languages for the specified repository.

        https://docs.github.com/en/enterprise-server@3.12/rest/repos/repos?apiVersion=2022-11-28#list-repository-languages

        Fine-grained access tokens require the "Metadata" repository permissions (read).
        """
        try:

            async for lang_resp in self._get_paginated(
                f"repos/{owner_login}/{repo_name}/languages"
            ):
                yield lang_resp

        except httpx.HTTPError as e:
            _fetch_problem(f"languages for repo {owner_login}/{repo_name}", e)

    async def fetch_webhooks_for_repo(
        self, owner_login: str, repo_name: str
    ) -> AsyncGenerator[types.Webhook]:
        """Try to get types.webhook data for this repo.

        https://docs.github.com/en/enterprise-server@3.12/rest/repos/webhooks?apiVersion=2022-11-28#list-repository-webhooks

        Fine-grained access tokens require the "Webhooks" repository permissions (read).
        """
        try:
            async for hook in self._get_paginated(
                f"repos/{owner_login}/{repo_name}/hooks"
            ):
                yield hook

        except httpx.HTTPError as e:
            _fetch_problem(f"webhooks for repo {owner_login}/{repo_name}", e)

    async def fetch_collaborators_for_repo(
        self,
        owner_login: str,
        repo_name: str,
    ) -> AsyncGenerator[types.GithubUser]:
        """Try to get collaborator data for this repo.

        For organization-owned repositories, the list of collaborators includes
        outside collaborators, organization members that are direct collaborators,
        organization members with access through team memberships, organization
        members with access through default organization permissions,
        and organization owners. Organization members with write, maintain, or admin
        privileges on the organization-owned repository can use this endpoint.

        https://docs.github.com/en/enterprise-server@3.12/rest/collaborators/collaborators?apiVersion=2022-11-28

        The authenticated user must have push access to the repository to use
        this endpoint.

        OAuth app tokens and personal access tokens (classic) need the `read:org`
        and `repo` scopes to use this endpoint.

        Fine-grained access tokens require the "Metadata" repository permissions (read)
        """
        try:
            async for collab_resp in self._get_paginated(
                f"repos/{owner_login}/{repo_name}/collaborators"
            ):
                yield collab_resp

        except httpx.HTTPError as e:
            _fetch_problem(f"collaborators for repo {owner_login}/{repo_name}", e)

    async def fetch_all_public_repos(self) -> AsyncGenerator[types.GithubRepo]:
        """
        Returns all public repositories in the order that they were created.

        Note:
            - For GitHub Enterprise Server, this endpoint will only list repositories
                available to all users on the enterprise.
            - Pagination is powered exclusively by the 'since' parameter. Use the
                Link header to get the URL for the next page of repositories.

        https://docs.github.com/en/enterprise-server@3.12/rest/repos/repos?apiVersion=2022-11-28#list-public-repositories

        If using a fine-grained access token, the token must have the
        "Metadata" repository permissions (read)
        """
        try:
            async for repo in self._get_paginated("repositories"):
                yield repo

        except httpx.HTTPError as e:
            _fetch_problem("all public repositories", e)

    async def fetch_all_users(self) -> AsyncGenerator[types.GithubUser]:
        """
        Fetches all users in the order that they were created.

        https://docs.github.com/en/enterprise-server@3.12/rest/users/users?apiVersion=2022-11-28#list-users
        """
        try:
            async for user in self._get_paginated("users"):
                if user["type"] == "User":
                    yield user
        except httpx.HTTPError as e:
            _fetch_problem("all users", e)

    async def fetch_teams_for_org(
        self, org_login: str
    ) -> AsyncGenerator[types.GithubTeamSummary]:
        """Fetch all teams in an organization visible to the authenticated user.

        https://docs.github.com/en/enterprise-server@3.12/rest/teams/teams?apiVersion=2022-11-28#list-teams

        Fine-grained tokens must have the "Members" organization permissions (read)
        """
        try:
            logger.debug("Fetch teams for %s", org_login)
            async for team_summary in self._get_paginated(
                f"orgs/{org_login}/teams",
            ):
                yield team_summary

        except httpx.HTTPError as e:
            _fetch_problem(f"teams for org {org_login}", e)

    async def fetch_team(self, org_login: str, slug: str) -> types.GithubTeam | None:
        """Fetches a single team for an org by the team slug.

        https://docs.github.com/en/enterprise-server@3.12/rest/teams/teams?apiVersion=2022-11-28#get-a-team-by-name
        """
        try:
            return await self._get_item(f"orgs/{org_login}/teams/{slug}")
        except httpx.HTTPError as e:
            _fetch_problem(f"full team info for {org_login}/{slug}", e)

    async def fetch_members_for_team(
        self, team_id: int, role: str | None = None
    ) -> AsyncGenerator[types.GithubUser]:
        """Fetch all users that have a given role for a specified team.

        These endpoints are only available to authenticated members of the
        team's organization.

        Access tokens require the read:org scope.

        To list members in a team, the team must be visible to the authenticated user.

        https://docs.github.com/en/enterprise-server@3.12/rest/teams/members?apiVersion=2022-11-28#list-team-members-legacy
        """
        try:
            params = {}
            if role:
                params["role"] = role
            async for member in self._get_paginated(
                f"teams/{team_id}/members", params=params
            ):
                yield member
        except httpx.HTTPError as e:
            _fetch_problem(f"members for team {team_id}", e)

    async def fetch_repos_for_team(
        self, org_login: str, slug: str
    ) -> AsyncGenerator[types.GithubRepo]:
        """Fetch all repos for a specified team visible to the authenticated user.

        These endpoints are only available to authenticated members of the
        team's organization.

        https://docs.github.com/en/enterprise-server@3.12/rest/teams/teams?apiVersion=2022-11-28#list-team-repositories
        """
        try:
            async for repo in self._get_paginated(
                f"orgs/{org_login}/teams/{slug}/repos"
            ):
                yield repo
        except httpx.HTTPError as e:
            _fetch_problem(f"repos for team {org_login}/{slug}", e)
