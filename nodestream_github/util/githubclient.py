"""githubclient

An async client for accessing GitHub.
"""

import logging
from enum import Enum
from typing import AsyncIterator

import httpx
from httpx import AsyncClient, Request, TransportError
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

from nodestream_github.types import (
    GithubOrg,
    GithubRepo,
    GithubTeam,
    GithubTeamSummary,
    GithubUser,
    JSONType,
    Webhook,
)

from .logutil import init_logger
from .permissions import PermissionCategory, PermissionName

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

        self._retryer = AsyncRetrying(
            wait=wait_random_exponential(),
            stop=stop_after_attempt(self.max_retries),
            retry=retry_if_exception_type((RateLimitedException, TransportError)),
            before_sleep=before_sleep_log(logger.logger, logging.WARNING),
            after=after_log(logger.logger, logging.WARNING),
            reraise=True,
        )

    async def log_metrics(self, method: str):
        waiting = await self.rate_limiter.get_window_stats(self.limit_per_second)
        logger.info(f"{method=}, {waiting=}")

    @property
    def retryer(self):
        return self._retryer

    async def _get(self, url: str):
        # nothing should ever call this directly, so it's hidden here
        async def _get_inner():
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

        return await self.retryer(_get_inner)

    async def _get_paginated(self, path: str, params=None) -> AsyncIterator[JSONType]:
        url = f"{self.github_endpoint}/{path}"
        logger.debug("GET (paginated): %s", url)
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

    async def _get_item(self, path):
        url = f"{self.github_endpoint}/{path}"
        logger.debug("GET: %s", url)
        response = await self._get(url)

        if response:
            return response.json()
        else:
            return {}

    async def fetch_repos_for_org(
        self, org_login, repo_type: str | None = None
    ) -> AsyncIterator[GithubRepo]:
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
            async for response in self._get_paginated(f"orgs/{org_login}/repos", params):
                yield response
        except httpx.HTTPStatusError as e:
            if e.response.status_code == httpx.codes.FORBIDDEN:
                logger.permission_warning(
                    "org repos",
                    org_login,
                    PermissionName.METADATA,
                    PermissionCategory.REPO,
                    exc_info=True,
                )
            else:
                logger.warning(
                    "Problem getting repos for org %s", org_login, exc_info=True
                )

        except httpx.HTTPError:
            logger.warning(
                "Major problem getting org repo info for %s",
                org_login,
                exc_info=True,
            )

    async def fetch_members_for_org(
        self, org_login: str, role: str | None = None
    ) -> AsyncIterator[GithubUser]:
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
            async for member in self._get_paginated(f"orgs/{org_login}/members", params):
                yield member
        except httpx.HTTPStatusError as e:
            if e.response.status_code == httpx.codes.FORBIDDEN:
                logger.permission_warning(
                    "org members",
                    org_login,
                    PermissionName.MEMBERS,
                    PermissionCategory.ORG,
                    exc_info=True,
                )
            else:
                logger.warning(
                    "Problem getting org members for %s", org_login, exc_info=True
                )
        except httpx.HTTPError:
            logger.warning(
                "Major problem getting org membership info for %s",
                org_login,
                exc_info=True,
            )

    async def fetch_all_organizations(self) -> AsyncIterator[GithubOrg]:
        """Fetches all organizations, in the order that they were created.

        https://docs.github.com/en/enterprise-server@3.12/rest/orgs/orgs?apiVersion=2022-11-28#list-organizations
        """
        try:
            async for org in self._get_paginated("organizations"):
                yield org
        except httpx.HTTPError:
            logger.warning(
                "Major problem getting list of all github organizations.", exc_info=True
            )

    async def fetch_full_org(self, org_login: str) -> GithubOrg | None:
        """Fetches the complete org record.

        https://docs.github.com/en/enterprise-server@3.12/rest/orgs/orgs?apiVersion=2022-11-28#get-an-organization

        Personal access tokens (classic) need the admin:org scope to see the
        full details about an organization.

        The fine-grained token does not require any permissions.
        """
        try:
            logger.debug(f"fetching full org={org_login}")
            return await self._get_item(f"orgs/{org_login}")
        except httpx.HTTPStatusError as e:
            if e.response.status_code == httpx.codes.FORBIDDEN:
                logger.warning(
                    "Current access token does not have permissions to get org details for %s",
                    org_login,
                    exc_info=True,
                )
            else:
                logger.warning(
                    "Problem getting full-org info for '%s'",
                    org_login,
                    exc_info=True,
                )

        except httpx.HTTPError:
            logger.warning(
                "Major problem getting full-org info for '%s'",
                org_login,
                exc_info=True,
            )

    async def fetch_repos_for_user(
        self,
        user_login: str,
        repo_type: str | None = None,
    ) -> AsyncIterator[GithubRepo]:
        """Fetches repositories for a user.

        https://docs.github.com/en/enterprise-server@3.12/rest/repos/repos?apiVersion=2022-11-28#list-repositories-for-a-user

        Fine-grained token must have the "Metadata" repository permissions (read)
        """
        try:
            params = {}
            if repo_type:
                params["type"] = repo_type
            async for repo in self._get_paginated(f"users/{user_login}/repos", params):
                yield repo
        except httpx.HTTPStatusError as e:
            if e.response.status_code == httpx.codes.FORBIDDEN:
                logger.permission_warning(
                    "user repos",
                    user_login,
                    PermissionName.METADATA,
                    PermissionCategory.REPO,
                    exc_info=True,
                )
            else:
                logger.warning("Problem getting user repos for '%s': %s", user_login, e)

        except httpx.HTTPError as e:
            logger.warning(
                "Major problem getting user repo info for '%s' (%s): %s",
                user_login,
                e.request.url,
                e,
            )

    async def fetch_languages_for_repo(
        self, owner_login: str, repo_name: str
    ) -> AsyncIterator[str]:
        """Fetch languages for the specified repository.

        https://docs.github.com/en/enterprise-server@3.12/rest/repos/repos?apiVersion=2022-11-28#list-repository-languages

        Fine-grained access tokens require the "Webhooks" repository permissions (read).
        """
        try:

            async for lang_resp in self._get_paginated(
                f"repos/{owner_login}/{repo_name}/languages"
            ):
                yield lang_resp
        except httpx.HTTPStatusError as e:
            if e.response.status_code == httpx.codes.FORBIDDEN:
                logger.permission_warning(
                    "repo languages",
                    f"{owner_login}/{repo_name}",
                    PermissionName.METADATA,
                    PermissionCategory.REPO,
                    exc_info=True,
                )
            else:
                logger.warning(
                    "Problem getting languages for %s/%s",
                    owner_login,
                    repo_name,
                    exc_info=True,
                )
        except httpx.HTTPError:
            logger.warning(
                "Problem getting languages for %s",
                owner_login,
                repo_name,
                exc_info=True,
            )

    async def fetch_webhooks_for_repo(
        self, owner_login: str, repo_name: str
    ) -> AsyncIterator[Webhook]:
        """Try to get webhook data for this repo.

        https://docs.github.com/en/enterprise-server@3.12/rest/repos/webhooks?apiVersion=2022-11-28#list-repository-webhooks

        Fine-grained access tokens require the "Webhooks" repository permissions (read).
        """
        try:
            async for hook in self._get_paginated(
                f"repos/{owner_login}/{repo_name}/webhooks"
            ):
                yield hook
        except httpx.HTTPStatusError as e:
            if e.response.status_code == httpx.codes.FORBIDDEN:
                logger.permission_warning(
                    "repo webhook",
                    f"{owner_login}/{repo_name}",
                    PermissionName.WEBHOOKS,
                    PermissionCategory.REPO,
                    exc_info=True,
                )
            else:
                logger.warning(
                    "Problem getting webhooks for %s/%s",
                    owner_login,
                    repo_name,
                    exc_info=True,
                )
        except httpx.HTTPError:
            logger.warning(
                "Problem getting webhooks for %s/%s",
                owner_login,
                repo_name,
                exc_info=True,
            )

    async def fetch_collaborators_for_repo(
        self,
        owner_login: str,
        repo_name: str,
    ) -> AsyncIterator[GithubUser]:
        """Try to get collaborator data for this repo.

        https://docs.github.com/en/enterprise-server@3.12/rest/collaborators/collaborators?apiVersion=2022-11-28

        Fine-grained access tokens require the "Metadata" repository permissions (read)
        """
        try:
            async for collab_resp in self._get_paginated(
                f"repos/{owner_login}/{repo_name}/collaborators"
            ):
                yield collab_resp

        except httpx.HTTPStatusError as e:
            if e.response.status_code == httpx.codes.FORBIDDEN:
                logger.permission_warning(
                    "repo collaborators",
                    f"{owner_login}/{repo_name}",
                    PermissionName.METADATA,
                    PermissionCategory.REPO,
                    exc_info=True,
                )
            else:
                logger.warning(
                    "Problem getting collaborators for %s/%s",
                    owner_login,
                    repo_name,
                    exc_info=True,
                )
        except httpx.HTTPError:
            logger.warning(
                "Problem getting collaborators for '%s': %s",
                owner_login,
                repo_name,
                exc_info=True,
            )

    async def fetch_all_public_repos(self) -> AsyncIterator[GithubRepo]:
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
        except httpx.HTTPError:
            logger.warning(
                "Major problem getting list of all public github repositories.",
                exc_info=True,
            )

    async def fetch_all_users(self) -> AsyncIterator[GithubUser]:
        """
        Fetches all users in the order that they were created.

        https://docs.github.com/en/enterprise-server@3.12/rest/users/users?apiVersion=2022-11-28#list-users
        """
        try:
            async for user in self._get_paginated("users"):
                yield user
        except httpx.HTTPError:
            logger.warning(
                "Major problem getting list of all github users",
                exc_info=True,
            )

    async def fetch_teams_for_org(self, org_login) -> AsyncIterator[GithubTeamSummary]:
        """Fetch all teams in an organization that are visible to the authenticated user.

        https://docs.github.com/en/enterprise-server@3.12/rest/teams/teams?apiVersion=2022-11-28#list-teams

        Fine-grained tokens must have the "Members" organization permissions (read)
        """
        try:
            logger.debug("Getting teams for %s", org_login)
            async for team_summary in self._get_paginated(
                f"orgs/{org_login}/teams",
            ):
                yield team_summary
        except httpx.HTTPStatusError as e:
            if e.response.status_code == httpx.codes.FORBIDDEN:
                logger.permission_warning(
                    "org teams",
                    org_login,
                    PermissionName.MEMBERS,
                    PermissionCategory.ORG,
                    exc_info=True,
                )
            else:
                logger.warning(
                    "Problem getting team info for org %s",
                    org_login,
                    exc_info=True,
                )
        except httpx.HTTPError:
            logger.warning(
                "Major problem getting team info for org %s",
                org_login,
                exc_info=True,
            )

    async def fetch_team(self, org_login: str, slug: str) -> GithubTeam | None:
        """Fetches a single team for an org by the team slug.

        https://docs.github.com/en/enterprise-server@3.12/rest/teams/teams?apiVersion=2022-11-28#get-a-team-by-name
        """
        try:
            return await self._get_item(f"orgs/{org_login}/teams/{slug}")
        except httpx.HTTPError:
            logger.warning(
                "Major problem getting team info for %s/%s",
                org_login,
                slug,
                exc_info=True,
            )

    async def fetch_members_for_team(
        self, team_id: int, role: str | None = None
    ) -> AsyncIterator[GithubUser]:
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
            async for member in self._get_paginated(f"teams/{team_id}/members", params):
                yield member
        except httpx.HTTPError:
            logger.warning(
                "Problem getting %smembers for team '%s'",
                f"{role} " if role else "",
                team_id,
                exc_info=True,
            )

    async def fetch_repos_for_team(
        self, org_login: str, slug: str
    ) -> AsyncIterator[GithubRepo]:
        """Fetch all repos for a specified team that are visible to the authenticated user.

        These endpoints are only available to authenticated members of the
        team's organization.

        https://docs.github.com/en/enterprise-server@3.12/rest/teams/teams?apiVersion=2022-11-28#list-team-repositories
        """
        try:
            async for repo in self._get_paginated(
                f"orgs/{org_login}/teams/{slug}/repos"
            ):
                yield repo
        except httpx.HTTPError:
            logger.warning(
                "Problem getting repos for team '%s/%s'",
                org_login,
                slug,
                exc_info=True,
            )
