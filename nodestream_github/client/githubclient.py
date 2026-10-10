"""githubclient

An async client for accessing GitHub.
"""

import json
import logging
import time
from collections.abc import AsyncGenerator, Callable
from enum import Enum
from typing import Any, NamedTuple

import httpx
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

import nodestream_github.types as types
from nodestream_github.logging import get_plugin_logger
from nodestream_github.types import enums

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


class RateLimitedError(httpx.HTTPError):
    """A request was blocked by the client's own limiter or by the server.

    `from_server` marks a limit the server reported. `wait_seconds` is the wait
    the server stated, when it stated one.
    """

    def __init__(
        self,
        url: str | httpx.URL,
        *,
        wait_seconds: float | None = None,
        from_server: bool = False,
    ):
        super().__init__(f"Rate limited when calling {url}")
        self.wait_seconds = wait_seconds
        self.from_server = from_server


def _safe_get_json_error_message(response: httpx.Response) -> str | None:
    try:
        return response.json().get("message")
    except AttributeError:
        # ignore if no message
        return json.dumps(response.json())
    except ValueError:
        # ignore if no json
        return response.text


def _header_int(response: httpx.Response, name: str) -> int | None:
    try:
        return int(response.headers[name])
    except (KeyError, ValueError):
        return None


def _is_rate_limit(response: httpx.Response) -> bool:
    """Tell a rate-limit response from a permission failure."""
    if response.status_code == httpx.codes.TOO_MANY_REQUESTS:
        return True
    if response.status_code != httpx.codes.FORBIDDEN:
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


def _stated_wait_seconds(response: httpx.Response) -> float | None:
    """The wait the server states, or None when it states none we can use."""
    wait = _header_int(response, "retry-after")
    if wait is None and _header_int(response, "x-ratelimit-remaining") == 0:
        reset = _header_int(response, "x-ratelimit-reset")
        if reset is not None:
            wait = reset - int(time.time())
    return _bounded_wait(wait)


class _RateLimitState(NamedTuple):
    limit: int
    remaining: int
    reset: int


def _read_rate_limit_state(response: httpx.Response) -> _RateLimitState | None:
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
    before_sleep_log(logger, _retry_log_level(retry_state))(retry_state)


def _log_after_attempt(retry_state: RetryCallState) -> None:
    after_log(logger, _retry_log_level(retry_state))(retry_state)


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
        case RateLimitedError():
            logger.warning("Gave up fetching %s: %s", title, e, stacklevel=2)
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

        self._user_cap = rate_limit_per_minute
        self._rate_limit_state: _RateLimitState | None = None
        pace = _pace_per_minute(self._user_cap, None, 0)
        self._rate_limit = RateLimitItemPerSecond(_requests_per_second(pace))
        logger.info("GitHub REST rate limit set to %s requests per minute", pace)
        self._rate_limiter = MovingWindowRateLimiter(self.limit_storage)
        self._session = httpx.AsyncClient()

        max_retry_wait_seconds = (
            DEFAULT_MAX_RETRY_WAIT_SECONDS
            if max_retry_wait_seconds is None
            else max_retry_wait_seconds
        )
        self._retryer = AsyncRetrying(
            wait=_wait_for_rate_limit(max_retry_wait_seconds),
            stop=stop_after_attempt(self.max_retries),
            retry=retry_if_exception_type((RateLimitedError, httpx.TransportError)),
            before_sleep=_log_before_sleep,
            after=_log_after_attempt,
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
        """The limit item in use. Its window follows the current pace."""
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
        now = time.time()
        state = self._rate_limit_state
        if state is not None and state.remaining == 0 and state.reset > now:
            raise RateLimitedError(
                url, wait_seconds=_bounded_wait(state.reset - now), from_server=True
            )
        pace = _pace_per_minute(self._user_cap, state, now)
        self._rate_limit = RateLimitItemPerSecond(_requests_per_second(pace))
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
        if (new_state := _read_rate_limit_state(response)) is not None:
            self._rate_limit_state = new_state
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            if _is_rate_limit(response):
                raise RateLimitedError(
                    url, wait_seconds=_stated_wait_seconds(response), from_server=True
                ) from e
            raise
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
            if "&page=100" in url:
                logger.warning(
                    "The GithubAPI has reached the maximum page size "
                    "of 100. The returned data may be incomplete for request: %s",
                    url,
                )

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
        self,
        *,
        org_login: str,
        repo_type: enums.OrgRepoType | None = None,
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
        self,
        *,
        org_login: str,
        role: enums.OrgMemberRole | None = None,
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

    async def fetch_enterprise_audit_log(
        self,
        enterprise_name: str,
        search_phrase: str | None = None,
    ) -> AsyncGenerator[types.GithubAuditLog]:
        """Fetches enterprise-wide audit log data
        https://docs.github.com/en/enterprise-server@3.14/rest/enterprise-admin/audit-log?apiVersion=2022-11-28#get-the-audit-log-for-an-enterprise
        """
        try:
            params = {"phrase": search_phrase} if search_phrase else {}
            async for audit in self._get_paginated(
                f"enterprises/{enterprise_name}/audit-log", params=params
            ):
                yield audit
        except httpx.HTTPError as e:
            _fetch_problem("audit log", e)

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
            return None

    async def fetch_repos_for_user(
        self,
        *,
        user_login: str,
        repo_type: enums.UserRepoType | None = None,
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
        self,
        *,
        owner_login: str,
        repo_name: str,
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
        self,
        *,
        owner_login: str,
        repo_name: str,
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
        *,
        owner_login: str,
        repo_name: str,
        affiliation: enums.CollaboratorAffiliation,
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
                f"repos/{owner_login}/{repo_name}/collaborators",
                params={"affiliation": affiliation},
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
        self,
        *,
        org_login: str,
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

    async def fetch_team(self, *, org_login: str, slug: str) -> types.GithubTeam | None:
        """Fetches a single team for an org by the team slug.

        https://docs.github.com/en/enterprise-server@3.12/rest/teams/teams?apiVersion=2022-11-28#get-a-team-by-name
        """
        try:
            return await self._get_item(f"orgs/{org_login}/teams/{slug}")
        except httpx.HTTPError as e:
            _fetch_problem(f"full team info for {org_login}/{slug}", e)
            return None

    async def fetch_members_for_team(
        self,
        *,
        team_id: int,
        role: enums.TeamMemberRole | None = None,
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
        self,
        *,
        org_login: str,
        slug: str,
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

    async def fetch_user(self, *, username: str) -> types.GithubUser | None:
        """
        Provides publicly available information about someone with a GitHub account.

        https://docs.github.com/en/enterprise-server@3.12/rest/users/users?apiVersion=2022-11-28#get-a-user
        """
        try:
            return await self._get_item(f"users/{username}")
        except httpx.HTTPError as e:
            _fetch_problem(f"full user info for {username}", e)
            return None

    async def fetch_teams_for_repo(self, *, owner_login: str, repo_name: str):
        """
        Lists the teams that have access to the specified repository and that
        are also visible to the authenticated user.

        For a public repository, a team is listed only if that team added the
        public repository explicitly.

        https://docs.github.com/en/enterprise-server@3.12/rest/repos/repos?apiVersion=2022-11-28#list-repository-teams
        """
        try:
            async for team in self._get_paginated(
                f"repos/{owner_login}/{repo_name}/teams"
            ):
                yield team
        except httpx.HTTPError as e:
            _fetch_problem(f"teams for repo {owner_login}/{repo_name}", e)

    async def fetch_branch_protection(
        self,
        *,
        owner_login: str,
        repo_name: str,
        branch: str,
    ) -> types.BranchProtection | None:
        """Fetches the branch protection for a given branch.

        https://docs.github.com/en/enterprise-server@3.12/rest/branches/branch-protection?apiVersion=2022-11-28#get-branch-protection
        """

        try:
            return await self._get_item(
                f"repos/{owner_login}/{repo_name}/branches/{branch}/protection"
            )
        except httpx.HTTPError as e:
            match e:
                case httpx.HTTPStatusError(response=response) if (
                    response.status_code == 404
                ):
                    logger.info(
                        "Branch protection not found for branch %s on repo %s/%s",
                        branch,
                        owner_login,
                        repo_name,
                    )
                case _:
                    _fetch_problem(
                        f"branch protection for branch {branch} on "
                        f"repo {owner_login}/{repo_name}",
                        e,
                    )
            return None
