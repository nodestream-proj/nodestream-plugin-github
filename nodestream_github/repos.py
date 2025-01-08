"""
Nodestream Extractor that creates GitHub repository nodes from the GitHub REST API.

Developed using Enterprise Server 3.12
https://docs.github.com/en/enterprise-server@3.12/rest?apiVersion=2022-11-28
"""

from dataclasses import dataclass
from typing import AsyncIterator

import httpx
from nodestream.pipeline import Extractor

from .interpretations.relationship.user import simplify_user
from .types import GithubRepo, LanguageRecord, RepositoryRecord, SimplifiedUser, Webhook
from .util import GithubRestApiClient, init_logger
from .util.permissions import PermissionCategory, PermissionName

logger = init_logger(__name__)


def _dict_val_to_bool(d: dict[str, any], key: str, default: bool = False) -> bool:
    value = d.get(key)
    if value is None:
        return default
    if isinstance(value, bool):
        return value

    return True  # key is present


@dataclass
class CollectWhichRepos:
    all_public: bool = False
    org_public: bool = False
    org_private: bool = False
    user_public: bool = False
    user_private: bool = False

    @property
    def org_any(self) -> bool:
        return self.org_public or self.org_private

    @property
    def user_any(self) -> bool:
        return self.user_public or self.user_private

    @classmethod
    def from_dict(cls, raw_input: dict[str, any]):
        org_all = _dict_val_to_bool(raw_input, "org_all", False)
        user_all = _dict_val_to_bool(raw_input, "user_all", False)

        return CollectWhichRepos(
            all_public=_dict_val_to_bool(raw_input, "all_public", False),
            org_public=org_all | _dict_val_to_bool(raw_input, "org_public", False),
            org_private=org_all | _dict_val_to_bool(raw_input, "org_private", False),
            user_public=user_all | _dict_val_to_bool(raw_input, "user_public", False),
            user_private=user_all | _dict_val_to_bool(raw_input, "user_private", False),
        )


class GithubReposExtractor(Extractor):
    def __init__(
        self,
        collecting: CollectWhichRepos | dict[str, any] | None = None,
        **kwargs,
    ):
        if isinstance(collecting, CollectWhichRepos):
            self.collecting = collecting
        elif isinstance(collecting, dict):
            self.collecting = CollectWhichRepos.from_dict(collecting)
        else:
            self.collecting = CollectWhichRepos()
        self.client = GithubRestApiClient(**kwargs)

    async def extract_records(self) -> AsyncIterator[RepositoryRecord]:
        logger.info("collecting: %s", self.collecting)
        if self.collecting.all_public:
            async for repo in self._fetch_public_repos():
                yield await self._extract_repo(repo)

        if self.collecting.org_any:
            async for repo in self._fetch_repos_by_org():
                yield await self._extract_repo(repo)

        if self.collecting.user_any:
            async for repo in self._fetch_repos_by_user():
                yield await self._extract_repo(repo)

    async def _extract_repo(self, repo: GithubRepo) -> RepositoryRecord:
        """Enhances raw GitHub json data into a dict that supports using it in pipelines."""
        logger.debug("Extracting repo %s", repo["full_name"])
        repo_full_name = repo["full_name"]
        owner = repo.get("owner", {})
        if owner.get("type") == "User":
            repo["user_owner"] = owner
        elif owner:
            repo["org_owner"] = owner
        repo["languages"] = [
            lang async for lang in self._fetch_languages(repo_full_name)
        ]
        repo["webhooks"] = [hook async for hook in self._fetch_webhooks(repo_full_name)]
        repo["collaborators"] = [
            user async for user in self._fetch_collaborators(repo_full_name)
        ]
        return repo

    async def _fetch_languages(
        self, repo_full_name: str
    ) -> AsyncIterator[LanguageRecord]:
        """Fetch languages for the specified repository.

        https://docs.github.com/en/enterprise-server@3.12/rest/repos/repos?apiVersion=2022-11-28#list-repository-languages

        Fine-grained access tokens require the "Webhooks" repository permissions (read).
        """
        try:

            async for lang_resp in self.client.get(f"repos/{repo_full_name}/languages"):
                yield {"name": lang_resp}
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 403:
                logger.permission_warning(
                    "repo languages",
                    repo_full_name,
                    PermissionName.METADATA,
                    PermissionCategory.REPO,
                    exc_info=True,
                )
            else:
                logger.warning(
                    "Problem getting languages for '%s': %s",
                    repo_full_name,
                    exc_info=True,
                )
        except httpx.HTTPError as e:
            logger.warning("Problem getting languages for '%s': %s", repo_full_name, e)

    async def _fetch_collaborators(
        self, repo_full_name: str
    ) -> AsyncIterator[SimplifiedUser]:
        """Try to get collaborator data for this repo.

        https://docs.github.com/en/enterprise-server@3.12/rest/collaborators/collaborators?apiVersion=2022-11-28

        Fine-grained access tokens require the "Metadata" repository permissions (read)
        """
        try:
            async for collab_resp in self.client.get(
                f"repos/{repo_full_name}/collaborators"
            ):
                yield simplify_user(collab_resp)

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 403:
                logger.permission_warning(
                    "repo collaborators",
                    repo_full_name,
                    PermissionName.METADATA,
                    PermissionCategory.REPO,
                    exc_info=True,
                )
            else:
                logger.warning(
                    "Problem getting collaborators for '%s': %s",
                    repo_full_name,
                    exc_info=True,
                )
        except httpx.HTTPError as e:
            logger.warning(
                "Problem getting collaborators for '%s': %s", repo_full_name, e
            )

    async def _fetch_webhooks(self, repo_full_name: str) -> AsyncIterator[Webhook]:
        """Try to get webhook data for this repo.

        https://docs.github.com/en/enterprise-server@3.12/rest/repos/webhooks?apiVersion=2022-11-28#list-repository-webhooks

        Fine-grained access tokens require the "Webhooks" repository permissions (read).
        """
        try:
            async for wh_resp in self.client.get(f"repos/{repo_full_name}/webhooks"):
                yield wh_resp
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 403:
                logger.permission_warning(
                    "repo webhook",
                    repo_full_name,
                    PermissionName.WEBHOOKS,
                    PermissionCategory.REPO,
                    exc_info=True,
                )
            else:
                logger.warning(
                    "Problem getting webhooks for '%s'", repo_full_name, exc_info=True
                )
        except httpx.HTTPError:
            logger.warning(
                "Problem getting webhooks for '%s'", repo_full_name, exc_info=True
            )

    async def _fetch_public_repos(self) -> AsyncIterator[GithubRepo]:
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
        async for repo in self.client.get("repositories"):
            yield repo

    async def _fetch_repos_by_org(self) -> AsyncIterator[GithubRepo]:
        logger.info("Fetching org repos... %s", self.collecting)
        async for org in self.client.get("organizations"):
            if self.collecting.org_public:
                async for repo in self._fetch_repos_for_org(org["login"], "public"):
                    yield await self._extract_repo(repo)
            if self.collecting.org_private:
                async for repo in self._fetch_repos_for_org(org["login"], "private"):
                    yield await self._extract_repo(repo)

    async def _fetch_repos_for_org(
        self, login: str, repo_type: str
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
            async for repo in self.client.get(
                f"orgs/{login}/repos", {"type": repo_type}
            ):
                yield repo
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 403:
                logger.permission_warning(
                    "org repos",
                    login,
                    PermissionName.METADATA,
                    PermissionCategory.REPO,
                    exc_info=True,
                )
            else:
                logger.warning(
                    "Problem getting org repos for '%s': %s", login, exc_info=True
                )

        except httpx.HTTPError:
            logger.warning(
                "Major problem getting org repo info for '%s'",
                login,
                exc_info=True,
            )

    async def _fetch_repos_by_user(self) -> AsyncIterator[GithubRepo]:
        """Fetches repositories for the specified user.

        https://docs.github.com/en/enterprise-server@3.12/rest/repos/repos?apiVersion=2022-11-28#list-repositories-for-a-user

        If using a fine-grained access token, the token must have the "Metadata"
        repository permissions (read)
        """
        async for user in self.client.get("users"):
            if self.collecting.user_public:
                async for repo in self._fetch_repos_for_user(user["login"], "public"):
                    yield await self._extract_repo(repo)
            if self.collecting.user_private:
                async for repo in self._fetch_repos_for_user(user["login"], "private"):
                    yield await self._extract_repo(repo)

    async def _fetch_repos_for_user(
        self, login: str, repo_type: str
    ) -> AsyncIterator[GithubRepo]:
        """Fetches repositories for a user"""
        try:
            async for repo in self.client.get(
                f"users/{login}/repos", {"type": repo_type}
            ):
                yield repo
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 403:
                logger.permission_warning(
                    "user repos",
                    login,
                    PermissionName.METADATA,
                    PermissionCategory.REPO,
                    exc_info=True,
                )
            else:
                logger.warning("Problem getting user repos for '%s': %s", login, e)

        except httpx.HTTPError as e:
            logger.warning(
                "Major problem getting user repo info for '%s' (%s): %s",
                login,
                e.request.url,
                e,
            )
